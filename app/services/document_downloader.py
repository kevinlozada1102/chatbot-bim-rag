# app/services/document_downloader.py
import os
import hashlib
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SmartDownloader:
    """Gestor de descarga inteligente con cache para documentos"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or os.getenv('CACHE_DIR', './cache/files'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_cache_age_days = 7
        
    def _generate_cache_filename(self, url: str, record_id: int) -> str:
        """Genera nombre único para archivo en cache"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        extension = self._get_extension_from_url(url)
        return f"doc_{record_id}_{url_hash}{extension}"
    
    def _get_extension_from_url(self, url: str) -> str:
        """Extrae extensión del archivo desde URL"""
        # Casos especiales: Google Drive
        if 'drive.google.com/uc' in url or 'drive.google.com/file' in url:
            # URLs de Google Drive son PDFs si fueron convertidas
            return '.pdf'

        # Detección estándar por extensión en la URL
        if url.lower().endswith('.pdf'):
            return '.pdf'
        elif any(url.lower().endswith(ext) for ext in ['.html', '.htm']):
            return '.html'
        elif url.lower().endswith('.docx'):
            return '.docx'
        elif url.lower().endswith('.doc'):
            return '.doc'
        else:
            # Default para URLs sin extensión clara
            return '.pdf'  # Asumir PDF por defecto en lugar de .txt
    
    def _is_fresh(self, file_path: Path) -> bool:
        """Verifica si el archivo cacheado es reciente"""
        if not file_path.exists():
            return False
        
        file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
        return file_age < timedelta(days=self.max_cache_age_days)
    
    async def get_or_download_file(self, url: str, record_id: int) -> Optional[str]:
        """
        Obtiene archivo desde cache o lo descarga si es necesario
        
        Args:
            url: URL del documento
            record_id: ID del registro en BD
            
        Returns:
            Ruta local del archivo o None si falló
        """
        try:
            filename = self._generate_cache_filename(url, record_id)
            cache_path = self.cache_dir / filename
            
            # Si existe en cache y es reciente, usarlo
            if self._is_fresh(cache_path):
                logger.info(f"Using cached file for record {record_id}: {cache_path}")
                return str(cache_path)
            
            # Descargar archivo
            logger.info(f"Downloading file for record {record_id} from {url}")
            success = await self._download_file(url, cache_path)
            
            if success:
                return str(cache_path)
            else:
                # Fallback: usar versión cacheada aunque sea vieja
                if cache_path.exists():
                    logger.warning(f"Download failed, using old cached version: {cache_path}")
                    return str(cache_path)
                return None
                
        except Exception as e:
            logger.error(f"Error in get_or_download_file: {e}")
            return None
    
    async def _download_file(self, url: str, destination: Path) -> bool:
        """Descarga archivo desde URL con técnicas anti-bot bypass"""
        try:
            timeout = aiohttp.ClientTimeout(total=60)  # 60 segundos timeout

            # Headers para simular navegador real
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'DNT': '1'
            }

            connector = aiohttp.TCPConnector(ssl=False, limit=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector) as session:
                async with session.get(url, ssl=False) as response:
                    if response.status == 200:
                        # Detectar tipo real del archivo desde Content-Type
                        content_type = response.headers.get('Content-Type', '').lower()
                        logger.info(f"📦 Downloading file - Content-Type: {content_type}")

                        # Determinar extensión correcta basada en Content-Type
                        correct_extension = None
                        if 'application/pdf' in content_type:
                            correct_extension = '.pdf'
                        elif 'application/msword' in content_type or 'application/vnd.openxmlformats-officedocument.wordprocessingml' in content_type:
                            correct_extension = '.docx' if 'openxmlformats' in content_type else '.doc'

                        # Si la extensión detectada difiere, renombrar
                        final_destination = destination
                        if correct_extension and not str(destination).endswith(correct_extension):
                            final_destination = destination.with_suffix(correct_extension)
                            logger.info(f"🔄 Correcting file extension from {destination.suffix} to {correct_extension}")

                        async with aiofiles.open(final_destination, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)

                        logger.info(f"✅ Successfully downloaded {url} to {final_destination}")
                        return True
                    else:
                        logger.error(f"❌ Failed to download {url}, status: {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading {url}")
            return False
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False
    
    def clean_old_cache(self) -> int:
        """Limpia archivos de cache antiguos"""
        cleaned = 0
        try:
            cutoff_time = datetime.now() - timedelta(days=self.max_cache_age_days * 2)
            
            for file_path in self.cache_dir.glob("*"):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        cleaned += 1
                        logger.info(f"Cleaned old cache file: {file_path}")
                        
        except Exception as e:
            logger.error(f"Error cleaning cache: {e}")
            
        return cleaned
    
    def get_cache_stats(self) -> dict:
        """Obtiene estadísticas del cache"""
        try:
            files = list(self.cache_dir.glob("*"))
            total_files = len([f for f in files if f.is_file()])
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            return {
                "total_files": total_files,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}