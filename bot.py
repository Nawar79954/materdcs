import os
import sys
import logging
import tempfile
import re
import time
import urllib.parse
import threading
import shutil
import subprocess
import glob
import requests
import json
import random

# ========== Advanced Cloud Settings ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/bot.log')
    ]
)
logger = logging.getLogger(__name__)

print("🚀 Starting Advanced Media Bot on Railway...")

# ========== Install Required Packages ==========
def install_required_packages():
    """Install all required packages"""
    packages = [
        'pyTelegramBotAPI',
        'yt-dlp',
        'pillow',
        'requests',
        'psutil'
    ]
    
    for package in packages:
        try:
            if package == 'pyTelegramBotAPI':
                import telebot
                print("✅ telebot - already installed")
            elif package == 'yt-dlp':
                import yt_dlp
                print("✅ yt-dlp - already installed")
            elif package == 'pillow':
                from PIL import Image
                print("✅ pillow - already installed")
            elif package == 'requests':
                import requests
                print("✅ requests - already installed")
            elif package == 'psutil':
                import psutil
                print("✅ psutil - already installed")
        except ImportError:
            print(f"📦 Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_required_packages()

# ========== Import Libraries ==========
import telebot
from telebot import types
import yt_dlp
from PIL import Image
import psutil

# ========== Configuration ==========
API_TOKEN = os.environ.get('BOT_TOKEN')
if not API_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found in environment variables!")
    sys.exit(1)

print(f"✅ Bot token loaded successfully")

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Temporary directory for cloud
TEMP_DIR = "/tmp/telegram_bot_files"
os.makedirs(TEMP_DIR, exist_ok=True)

CLOUD_DEPLOYMENT = 'RAILWAY_ENVIRONMENT' in os.environ

print(f"🌐 Cloud Deployment: {CLOUD_DEPLOYMENT}")
print(f"📁 Temp Directory: {TEMP_DIR}")

# ========== User Management ==========
user_states = {}

# ========== FFmpeg Setup ==========
def setup_environment():
    """Setup environment including FFmpeg"""
    try:
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg is available")
            return True
        else:
            print("⚠️ FFmpeg not found, some features will be limited")
            return False
    except Exception as e:
        print(f"❌ Environment setup error: {e}")
        return False

FFMPEG_AVAILABLE = setup_environment()

# ========== FIXED yt-dlp Configuration ==========
def get_ydl_options(download_type='video', quality='best'):
    """Get FIXED yt-dlp options that actually download content"""
    
    base_options = {
        'outtmpl': os.path.join(TEMP_DIR, '%(title).100s.%(ext)s'),
        'quiet': False,  # Changed to False to see download progress
        'no_warnings': False,
        
        # Critical fixes for empty files
        'socket_timeout': 60,
        'retries': 20,
        'fragment_retries': 20,
        'skip_unavailable_fragments': False,  # Changed to False
        'ignoreerrors': False,
        'no_check_certificate': True,
        
        # Force download options
        'extract_flat': False,  # Must be False to actually download
        'force_json': False,
        'force_ipv4': True,
        
        # Browser simulation with better headers
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        },
        
        'noplaylist': True,
        
        # Downloader options
        'buffersize': 1024 * 1024,  # 1MB buffer
        'http_chunk_size': 10485760,  # 10MB chunks
    }
    
    # Audio specific options
    if download_type == 'audio':
        base_options.update({
            'format': 'bestaudio/best',
            'writethumbnail': False,
            'embed_metadata': True,
        })
        
        if FFMPEG_AVAILABLE:
            base_options.update({
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    },
                    {
                        'key': 'FFmpegMetadata',
                    }
                ],
                'prefer_ffmpeg': True,
            })
        else:
            # Fallback without FFmpeg
            base_options.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
    
    # Video specific options  
    else:
        if quality == 'fast':
            base_options.update({
                'format': 'best[height<=480]/best[height<=360]/worst',
            })
        elif quality == 'hd':
            base_options.update({
                'format': 'best[height<=1080]/best[height<=720]/best',
            })
        else:  # best
            base_options.update({
                'format': 'best[height<=720]/best[height<=480]/best',
            })
    
    return base_options

# ========== COMPLETELY REVISED Download Function ==========
def download_media(chat_id, url, download_type='video', quality='best'):
    """Completely revised download function with proper file verification"""
    
    max_retries = 3
    downloaded_file_path = None
    
    for attempt in range(max_retries):
        try:
            # Send progress update
            if attempt > 0:
                bot.send_message(chat_id, f"🔄 Retry attempt {attempt + 1}/{max_retries}...")
            else:
                bot.send_message(chat_id, "🔍 <b>Starting download process...</b>")
            
            # Get download options
            ydl_opts = get_ydl_options(download_type, quality)
            
            # Create a custom filename to track the download
            timestamp = int(time.time())
            if download_type == 'audio':
                ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'download_{timestamp}_%(title)s.%(ext)s')
            else:
                ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'download_{timestamp}_%(title)s.%(ext)s')
            
            print(f"🎯 Download attempt {attempt + 1} with options: {ydl_opts['format']}")
            
            # First, extract info to verify the video is accessible
            with yt_dlp.YoutubeDL({**ydl_opts, 'skip_download': True}) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        raise Exception("Could not extract video information")
                    
                    title = sanitize_filename(info.get('title', 'Unknown'))
                    duration = info.get('duration', 0)
                    
                    bot.send_message(chat_id, f"📥 <b>Downloading:</b> {title}\n⏱️ <b>Duration:</b> {format_duration(duration)}")
                    
                except Exception as e:
                    logger.error(f"Info extraction failed: {e}")
                    raise Exception(f"Cannot access video: {str(e)}")
            
            # Now perform the actual download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        # Only send progress updates occasionally to avoid spam
                        if random.random() < 0.1:  # 10% chance
                            try:
                                if '_percent_str' in d:
                                    bot.send_chat_action(chat_id, 'upload_video' if download_type != 'audio' else 'upload_audio')
                            except:
                                pass
                
                ydl.add_progress_hook(progress_hook)
                ydl.download([url])
            
            # Find the downloaded file - CRITICAL FIX
            time.sleep(2)  # Wait for file to be fully written
            
            # Look for files with our timestamp pattern
            pattern = os.path.join(TEMP_DIR, f"download_{timestamp}_*")
            files = glob.glob(pattern)
            
            if not files:
                # Fallback: get all files and find the newest one
                all_files = glob.glob(os.path.join(TEMP_DIR, "*"))
                if all_files:
                    # Sort by modification time, newest first
                    all_files.sort(key=os.path.getmtime, reverse=True)
                    files = [all_files[0]] if all_files else []
            
            # Verify the file is not empty
            for file_path in files:
                try:
                    file_size = os.path.getsize(file_path)
                    print(f"📁 Found file: {file_path} (Size: {file_size} bytes)")
                    
                    if file_size > 1024:  # File must be at least 1KB
                        downloaded_file_path = file_path
                        print(f"✅ Valid file found: {file_path} ({file_size} bytes)")
                        break
                    else:
                        print(f"❌ File too small: {file_path} ({file_size} bytes)")
                        try:
                            os.unlink(file_path)
                        except:
                            pass
                except Exception as e:
                    print(f"❌ Error checking file {file_path}: {e}")
                    continue
            
            if downloaded_file_path:
                return info, downloaded_file_path
            else:
                raise Exception("Download completed but no valid file found")
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Download error (attempt {attempt + 1}): {error_msg}")
            
            # Clean up any partial files
            try:
                pattern = os.path.join(TEMP_DIR, f"download_{timestamp}_*")
                for file_path in glob.glob(pattern):
                    os.unlink(file_path)
            except:
                pass
            
            if "HTTP Error 403" in error_msg or "Forbidden" in error_msg:
                if attempt < max_retries - 1:
                    # Try different format on retry
                    continue
                else:
                    raise Exception("Server blocked the request. Please try a different video or try again later.")
            elif "Video unavailable" in error_msg or "Private video" in error_msg:
                raise Exception("Video is unavailable, private, or restricted.")
            else:
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                else:
                    raise Exception(f"Download failed: {error_msg[:100]}")
                    
        except Exception as e:
            logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
            
            # Clean up any partial files
            try:
                pattern = os.path.join(TEMP_DIR, f"download_{timestamp}_*")
                for file_path in glob.glob(pattern):
                    os.unlink(file_path)
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                raise e
    
    raise Exception("All download attempts failed - no content received")

# ========== FIXED Download Handler ==========
def handle_download_process(chat_id, url, download_type='video', quality='best'):
    """Fixed download handler with proper file verification"""
    try:
        # Validate URL first
        if not is_supported_url(url):
            bot.send_message(chat_id, "❌ <b>Unsupported URL</b>\n\nSupported platforms: YouTube, Instagram, TikTok, Facebook, Twitter, SoundCloud, etc.")
            show_main_menu(chat_id)
            return
        
        bot.send_message(chat_id, "🔍 <b>Verifying URL and starting download...</b>")
        
        # Start download
        info, file_path = download_media(chat_id, url, download_type, quality)
        
        if not info or not file_path:
            bot.send_message(chat_id, "❌ <b>Download failed - No content received</b>")
            show_main_menu(chat_id)
            return
        
        # Verify file exists and has content
        if not os.path.exists(file_path):
            bot.send_message(chat_id, "❌ <b>Downloaded file not found</b>")
            show_main_menu(chat_id)
            return
        
        file_size = os.path.getsize(file_path)
        if file_size < 1024:  # Less than 1KB
            bot.send_message(chat_id, "❌ <b>Downloaded file is empty or too small</b>")
            try:
                os.unlink(file_path)
            except:
                pass
            show_main_menu(chat_id)
            return
        
        # Prepare file info
        title = sanitize_filename(info.get('title', 'Unknown'))
        file_size_str = get_file_size(file_path)
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'Unknown')
        
        caption = f"""
✅ <b>Download Complete!</b>

🎬 <b>Title:</b> {title}
👤 <b>Uploader:</b> {uploader}
⏱️ <b>Duration:</b> {format_duration(duration)}
📊 <b>Size:</b> {file_size_str}
        """
        
        # Send file with progress
        bot.send_message(chat_id, "📤 <b>Uploading file to Telegram...</b>")
        bot.send_chat_action(chat_id, 'upload_document')
        
        max_upload_attempts = 2
        upload_success = False
        
        for upload_attempt in range(max_upload_attempts):
            try:
                with open(file_path, 'rb') as file:
                    if download_type == 'audio':
                        bot.send_audio(chat_id, file, caption=caption, title=title[:64], timeout=120)
                    else:
                        bot.send_video(chat_id, file, caption=caption, timeout=120, supports_streaming=True)
                
                upload_success = True
                bot.send_message(chat_id, "✅ <b>Upload successful!</b>")
                break
                
            except Exception as upload_error:
                logger.error(f"Upload attempt {upload_attempt + 1} failed: {upload_error}")
                
                if upload_attempt < max_upload_attempts - 1:
                    bot.send_message(chat_id, f"⚠️ Upload failed, retrying... (Attempt {upload_attempt + 2})")
                    time.sleep(2)
                else:
                    # Final fallback: send as document
                    try:
                        with open(file_path, 'rb') as file:
                            bot.send_document(chat_id, file, caption=caption, timeout=120)
                        bot.send_message(chat_id, "✅ <b>Upload completed as document!</b>")
                        upload_success = True
                    except Exception as doc_error:
                        logger.error(f"Document upload also failed: {doc_error}")
                        bot.send_message(chat_id, f"❌ <b>Upload failed:</b> {str(upload_error)[:100]}")
        
        # Cleanup
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download processing error: {error_msg}")
        
        # User-friendly error messages
        if "unavailable" in error_msg.lower() or "private" in error_msg.lower():
            bot.send_message(chat_id, "❌ <b>Video unavailable</b> - The video may be private, deleted, or restricted.")
        elif "blocked" in error_msg.lower() or "403" in error_msg:
            bot.send_message(chat_id, "❌ <b>Access blocked</b> - The server is blocking requests. Please try a different video.")
        elif "No content" in error_msg or "empty" in error_msg.lower():
            bot.send_message(chat_id, "❌ <b>No content received</b> - The download completed but the file was empty.")
        else:
            bot.send_message(chat_id, f"❌ <b>Download error:</b>\n{error_msg[:150]}")
    
    finally:
        show_main_menu(chat_id)

# ========== Utility Functions ==========
def sanitize_filename(filename):
    """Sanitize filename for safe usage"""
    if not filename:
        return "media_file"
    
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename or "media_file"

def get_file_size(file_path):
    """Get human readable file size"""
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "Unknown"

def format_duration(seconds):
    """Format duration from seconds"""
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return "Unknown"

def is_supported_url(url):
    """Check if URL is from supported platform"""
    try:
        url = url.strip()
        if not url:
            return False
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        supported_domains = [
            'youtube.com', 'youtu.be', 'music.youtube.com',
            'instagram.com', 'www.instagram.com',
            'facebook.com', 'fb.watch', 'www.facebook.com',
            'tiktok.com', 'vm.tiktok.com', 'www.tiktok.com',
            'twitter.com', 'x.com', 'www.twitter.com',
            'soundcloud.com', 'www.soundcloud.com',
            'vimeo.com', 'www.vimeo.com',
            'dailymotion.com', 'www.dailymotion.com',
        ]
        
        domain = urllib.parse.urlparse(url).netloc.lower()
        return any(supported in domain for supported in supported_domains)
        
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False

# ========== Cleanup System ==========
class CleanupManager:
    def __init__(self):
        self.active = True
        
    def cleanup_old_files(self, max_age_minutes=10):  # Reduced to 10 minutes for faster cleanup
        """Clean up old temporary files"""
        try:
            current_time = time.time()
            deleted_files = 0
            
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(file_path):
                    file_age = (current_time - os.path.getctime(file_path)) / 60
                    if file_age > max_age_minutes:
                        try:
                            file_size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            deleted_files += 1
                            logger.info(f"Deleted {filename} ({file_size} bytes)")
                        except Exception as e:
                            logger.error(f"Failed to delete {filename}: {e}")
            
            if deleted_files > 0:
                logger.info(f"🧹 Cleaned {deleted_files} temporary files")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def start_cleanup_daemon(self):
        """Start background cleanup daemon"""
        def daemon_loop():
            while self.active:
                try:
                    self.cleanup_old_files()
                    time.sleep(300)  # 5 minutes
                except Exception as e:
                    logger.error(f"Cleanup daemon error: {e}")
                    time.sleep(300)
        
        thread = threading.Thread(target=daemon_loop, daemon=True)
        thread.start()
        logger.info("✅ Cleanup daemon started")

# Initialize cleanup system
cleanup_manager = CleanupManager()
cleanup_manager.start_cleanup_daemon()

# ========== Menu System ==========
def show_main_menu(chat_id):
    """Display the main menu"""
    try:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        buttons = [
            '📥 Download Video', 
            '⚡ Fast Download',
            '🎵 Audio Only',
            '🔍 Search Music',
            '📊 Status',
            'ℹ️ Help'
        ]
        
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            markup.add(*[types.KeyboardButton(btn) for btn in row])
        
        welcome_text = """
🎉 <b>Welcome to MasTerDCS</b>

⚡ <b>Available Features:</b>

• <b>Download Video</b> - High quality (720p)
• <b>Fast Download</b> - Lower quality for speed  
• <b>Audio Only</b> - Extract audio from videos
• <b>Search Music</b> - Find songs by lyrics/name


<code>Choose your desired option below 👇</code>
        """
        
        bot.send_message(chat_id, welcome_text, reply_markup=markup)
        user_states[chat_id] = 'main'
        
    except Exception as e:
        logger.error(f"Menu error: {e}")

# ========== Command Handlers ==========
@bot.message_handler(commands=['start', 'help', 'menu'])
def handle_start(message):
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text in ['📥 Download Video', '⚡ Fast Download', '🎵 Audio Only'])
def handle_download_selection(message):
    chat_id = message.chat.id
    
    configs = {
        '📥 Download Video': {'type': 'video', 'quality': 'best', 'desc': 'High Quality Video Download'},
        '⚡ Fast Download': {'type': 'video', 'quality': 'fast', 'desc': 'Fast Download (Lower Quality)'},
        '🎵 Audio Only': {'type': 'audio', 'quality': 'best', 'desc': 'Audio Extraction from Video'}
    }
    
    config = configs[message.text]
    user_states[chat_id] = f'waiting_url_{config["type"]}_{config["quality"]}'
    
    instructions = f"""
📋 <b>{config['desc']}</b>

🔗 <b>Send the video URL now</b>

🌐 <b>Supported Platforms:</b>
• YouTube, Instagram, TikTok
• Facebook, Twitter, SoundCloud  
• Vimeo, DailyMotion

💡 <b>Fixed Features:</b>
• Proper file verification
• No empty downloads
• Multiple retry attempts

<code>Paste your URL below...</code>
    """
    
    bot.send_message(chat_id, instructions, reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, '').startswith('waiting_url_'))
def process_url_input(message):
    chat_id = message.chat.id
    url = message.text.strip()
    
    current_state = user_states.get(chat_id, '')
    if not current_state.startswith('waiting_url_'):
        return
    
    parts = current_state.split('_')
    download_type = parts[2]
    quality = parts[3]
    
    user_states[chat_id] = 'processing'
    
    thread = threading.Thread(
        target=handle_download_process,
        args=(chat_id, url, download_type, quality)
    )
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 <b>Starting verified download process...</b>")

# ========== Music Search System ==========
@bot.message_handler(func=lambda message: message.text == '🔍 Search Music')
def handle_music_search(message):
    user_states[message.chat.id] = 'waiting_music_query'
    bot.send_message(
        message.chat.id,
        "🎵 <b>Music Search</b>\n\nSend song lyrics or title to search:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_music_query')
def process_music_search(message):
    chat_id = message.chat.id
    query = message.text.strip()
    
    if len(query) < 2:
        bot.send_message(chat_id, "❌ <b>Please enter at least 2 characters</b>")
        show_main_menu(chat_id)
        return
    
    try:
        bot.send_message(chat_id, f"🔍 <b>Searching for:</b> <code>{query}</code>")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 15,
        }
        
        search_url = f"ytsearch3:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                bot.send_message(chat_id, "❌ <b>No results found</b>")
                show_main_menu(chat_id)
                return
            
            entries = [e for e in info['entries'] if e and e.get('duration', 0) < 1800][:3]
            
            if not entries:
                bot.send_message(chat_id, "❌ <b>No valid results found</b>")
                show_main_menu(chat_id)
                return
            
            results_text = "🎵 <b>Top Results:</b>\n\n"
            for i, entry in enumerate(entries, 1):
                title = entry.get('title', 'Unknown Title')
                duration = format_duration(entry.get('duration'))
                results_text += f"{i}. {title}\n   ⏱️ {duration}\n\n"
            
            results_text += "⬇️ <b>Downloading first result...</b>"
            bot.send_message(chat_id, results_text)
            
            first_result = entries[0]
            handle_download_process(chat_id, first_result['url'], 'audio', 'best')
            
    except Exception as e:
        logger.error(f"Music search error: {e}")
        bot.send_message(chat_id, f"❌ <b>Search error:</b> {str(e)[:100]}")
        show_main_menu(chat_id)

# ========== Additional Handlers ==========
@bot.message_handler(func=lambda message: message.text == '📊 Status')
def handle_status(message):
    status_text = """
📊 <b>System Status</b>

✅ <b>All Systems Operational</b>

🔧 <b>Fixed Issues:</b>
• Empty file downloads - ✅ RESOLVED
• File verification - ✅ ACTIVE
• Download retries - ✅ ENABLED
• Proper cleanup - ✅ ACTIVE

🌐 <b>Platform Support:</b>
• YouTube, Instagram, TikTok
• Facebook, Twitter, SoundCloud
• Vimeo, DailyMotion

🚀 <b>Ready for verified downloads!</b>
    """
    
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help')
def handle_help(message):
    help_text = """
🛠️ <b>Fixed Media Bot - Help Guide</b>

⚡ <b>Download Options:</b>
• <b>Download Video</b> - High quality with verification
• <b>Fast Download</b> - Lower quality, faster download
• <b>Audio Only</b> - Extract audio from videos

🔍 <b>Music Search:</b>
• Search by lyrics or song title
• Automatic download of best match

🔧 <b>Fixed Features:</b>
• File size verification before upload
• Multiple download retry attempts
• Proper error handling
• No more empty files

💡 <b>Tips:</b>
• If download fails, it will auto-retry
• Files are verified before sending
• Large videos may take longer

<code>Choose any option from the main menu!</code>
    """
    
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(func=lambda message: True)
def handle_unknown_messages(message):
    """Handle unknown messages"""
    if message.chat.id not in user_states:
        show_main_menu(message.chat.id)
    else:
        bot.send_message(
            message.chat.id,
            "❌ <b>Unknown command</b>\n\nPlease use the menu buttons or type /help for assistance."
        )

# ========== Main Execution ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting FIXED Media Bot...")
    print(f"🌐 Cloud Environment: {CLOUD_DEPLOYMENT}")
    print(f"📁 Temporary Directory: {TEMP_DIR}")
    print(f"🔧 FFmpeg Available: {FFMPEG_AVAILABLE}")
    print("=" * 60)
    print("🔧 CRITICAL FIXES APPLIED:")
    print("   • File download verification")
    print("   • No more empty files") 
    print("   • Proper yt-dlp configuration")
    print("   • Enhanced error handling")
    print("=" * 60)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot initialized: @{bot_info.username}")
        
        cleanup_manager.cleanup_old_files(max_age_minutes=0)
        
        print("📊 Fixed bot is ready to receive requests...")
        print("=" * 60)
        
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Bot crash: {e}")
    finally:
        print("🛑 Shutting down bot...")
        cleanup_manager.active = False
        print("✅ Bot stopped successfully")
