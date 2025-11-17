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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("🚀 Starting Multi-Function Bot...")

# Check and install required libraries
try:
    import telebot
    from telebot import types
    print("✅ telebot - loaded successfully")
except ImportError:
    print("📦 Installing telebot...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI"])
    import telebot
    from telebot import types

try:
    import yt_dlp
    print("✅ yt-dlp - loaded successfully")
except ImportError:
    print("📦 Installing yt-dlp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
    import yt_dlp

try:
    from PIL import Image
    print("✅ PIL - loaded successfully")
except ImportError:
    print("📦 Installing pillow...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image

# ========== Configuration ==========
API_TOKEN = '8526634581:AAHBOfZw1UlBwrao1Wf2nY4TRGCGpKnce4g'
bot = telebot.TeleBot(API_TOKEN)

TEMP_DIR = "temp_files"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

user_states = {}

# ========== FFmpeg Check ==========
def check_ffmpeg():
    """Check if FFmpeg is available in the system"""
    try:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            print(f"✅ FFmpeg found at: {ffmpeg_path}")
            try:
                result = subprocess.run([ffmpeg_path, "-version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    print(f"🎯 FFmpeg version: {version_line}")
                    return True
            except Exception:
                pass
            return True
        
        # Check common installation paths
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe", 
            r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        ]
        
        username = os.getenv('USERNAME')
        if username:
            common_paths.append(rf"C:\Users\{username}\ffmpeg\bin\ffmpeg.exe")
        
        for path in common_paths:
            if os.path.exists(path):
                print(f"✅ FFmpeg found at: {path}")
                ffmpeg_dir = os.path.dirname(path)
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
                return True
        
        # Try running ffmpeg directly
        try:
            result = subprocess.run(["ffmpeg", "-version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ FFmpeg working correctly")
                return True
        except:
            pass
            
        print("❌ FFmpeg not installed in PATH")
        print("💡 Use /ffmpeg_help for installation instructions")
        return False
        
    except Exception as e:
        print(f"❌ Error checking FFmpeg: {e}")
        return False

FFMPEG_AVAILABLE = check_ffmpeg()

# ========== Auto Cleanup System ==========
class AutoCleanup:
    def __init__(self):
        self.is_running = False
        self.cleanup_thread = None
    
    def start_auto_cleanup(self):
        """Start automatic cleanup every hour"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_scheduler, daemon=True)
        self.cleanup_thread.start()
        logger.info("🚀 Auto cleanup system started")
    
    def _cleanup_scheduler(self):
        """Cleanup scheduler"""
        while self.is_running:
            try:
                deleted_files = self.cleanup_temp_files()
                if deleted_files > 0:
                    logger.info(f"🧹 Auto cleanup - deleted {deleted_files} files")
                else:
                    logger.debug("🧹 Auto cleanup - no files to delete")
                
                time.sleep(3600)  # Wait 1 hour
            except Exception as e:
                logger.error(f"Auto cleanup error: {e}")
                time.sleep(300)  # Wait 5 minutes then retry
    
    def stop_auto_cleanup(self):
        """Stop auto cleanup"""
        self.is_running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        logger.info("🛑 Auto cleanup stopped")
    
    def cleanup_temp_files(self, max_age_minutes=60):
        """Clean temporary files older than specified minutes"""
        try:
            current_time = time.time()
            deleted_files = 0
            total_size = 0
            
            if not os.path.exists(TEMP_DIR):
                return 0
            
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(file_path):
                    try:
                        file_age = current_time - os.path.getctime(file_path)
                        file_age_minutes = file_age / 60
                        
                        if file_age_minutes > max_age_minutes:
                            file_size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            deleted_files += 1
                            total_size += file_size
                            logger.debug(f"Deleted: {filename} (age: {file_age_minutes:.1f} minutes)")
                    except Exception as e:
                        logger.error(f"Error deleting {filename}: {e}")
            
            if deleted_files > 0:
                size_mb = total_size / (1024 * 1024)
                logger.info(f"🧹 Deleted {deleted_files} temp files ({size_mb:.2f} MB)")
            
            return deleted_files
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return 0

# Initialize auto cleanup system
auto_cleanup = AutoCleanup()

# ========== Helper Functions ==========
def is_valid_url(url):
    """Validate URL with comprehensive domain checking"""
    try:
        # Clean the URL
        url = url.strip()
        if not url:
            return False
            
        # Add https:// if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Parse URL
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Remove www. if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Supported domains and patterns
        supported_domains = {
            'youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com',
            'instagram.com', 'www.instagram.com',
            'facebook.com', 'fb.com', 'fb.watch', 'www.facebook.com',
            'tiktok.com', 'vm.tiktok.com', 'www.tiktok.com',
            'twitter.com', 'x.com', 'www.twitter.com',
            'reddit.com', 'www.reddit.com',
            'soundcloud.com', 'www.soundcloud.com',
            'spotify.com', 'open.spotify.com',
            'vimeo.com', 'www.vimeo.com',
            'dailymotion.com', 'www.dailymotion.com',
            'twitch.tv', 'www.twitch.tv',
            'rumble.com', 'www.rumble.com',
            'bilibili.com', 'www.bilibili.com'
        }
        
        # Check if domain is supported
        if domain not in supported_domains:
            return False
            
        # Basic URL format validation
        url_pattern = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return re.match(url_pattern, url) is not None
        
    except Exception as e:
        logger.error(f"URL validation error for '{url}': {e}")
        return False

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

def clean_filename(filename):
    """Clean filename from invalid characters"""
    if not filename:
        return "unknown"
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def format_duration(duration):
    """Format duration from seconds to MM:SS"""
    try:
        if duration is None:
            return "Unknown"
        duration = int(duration)
        minutes = duration // 60
        seconds = duration % 60
        return f"{minutes}:{seconds:02d}"
    except:
        return "Unknown"

def test_url_with_ytdlp(url):
    """Test if URL is actually accessible with yt-dlp"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'extract_flat': True,
            'socket_timeout': 15,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info is not None
    except Exception as e:
        logger.error(f"URL test failed for {url}: {e}")
        return False

# ========== yt-dlp Settings ==========
def get_ydl_opts(download_type='video', is_fast=False):
    """Get yt-dlp options based on download type"""
    base_opts = {
        'outtmpl': os.path.join(TEMP_DIR, '%(title).100s.%(ext)s'),
        'retries': 3,
        'fragment_retries': 3,
        'skip_unavailable_fragments': True,
        'ignoreerrors': False,
        'quiet': True,
        'socket_timeout': 30,
        'noplaylist': True,
    }
    
    if download_type == 'audio':
        if FFMPEG_AVAILABLE:
            base_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            base_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
    elif is_fast:
        base_opts.update({
            'format': 'worst[height<=360]/worst',
        })
    else:
        base_opts.update({
            'format': 'best[height<=720]/best[height<=480]/best',
        })
    
    return base_opts

# ========== Download System ==========
def download_media(url, chat_id, download_type='video', is_fast=False):
    """Download media with comprehensive error handling"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            bot.send_message(chat_id, f"🔄 Processing (Attempt {attempt + 1}/{max_retries})...")
            
            ydl_opts = get_ydl_opts(download_type, is_fast)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info first
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("Cannot get video information")
                
                title = clean_filename(info.get('title', 'unknown'))
                duration = info.get('duration', 0)
                
                if duration > 1800:  # More than 30 minutes
                    bot.send_message(chat_id, "⚠️ Long video - this may take a while")
                
                bot.send_message(chat_id, f"📥 Downloading: {title}")
                
                # Start download
                ydl.download([url])
                
                # Find the downloaded file
                file_pattern = os.path.join(TEMP_DIR, f"{title}.*")
                files = glob.glob(file_pattern)
                
                if files:
                    file_path = files[0]
                    return info, file_path
                else:
                    # Fallback: get the newest file in temp directory
                    all_files = glob.glob(os.path.join(TEMP_DIR, "*"))
                    if all_files:
                        latest_file = max(all_files, key=os.path.getctime)
                        return info, latest_file
                    else:
                        raise Exception("Downloaded file not found")
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Download attempt {attempt + 1} failed: {error_msg}")
            
            # Handle FFmpeg related errors
            if "ffprobe" in error_msg.lower() or "ffmpeg" in error_msg.lower():
                bot.send_message(chat_id, "❌ FFmpeg error! Downloading without conversion...")
                ydl_opts = get_ydl_opts('audio', is_fast)
                if 'postprocessors' in ydl_opts:
                    del ydl_opts['postprocessors']
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                        files = glob.glob(os.path.join(TEMP_DIR, "*"))
                        if files:
                            latest_file = max(files, key=os.path.getctime)
                            return info, latest_file
                except Exception as inner_e:
                    logger.error(f"Download without FFmpeg failed: {inner_e}")
                    break
                
            if attempt < max_retries - 1:
                bot.send_message(chat_id, f"⚠️ Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                raise e
    
    return None, None

def process_download(chat_id, url, media_type, is_fast=False):
    """Process download with comprehensive error handling"""
    try:
        bot.send_message(chat_id, "🔍 Validating URL...")
        
        # Validate URL format
        if not is_valid_url(url):
            bot.send_message(chat_id, "❌ Invalid URL format or unsupported platform")
            send_welcome_by_id(chat_id)
            return
        
        # Test URL accessibility
        bot.send_message(chat_id, "🌐 Testing connection...")
        if not test_url_with_ytdlp(url):
            bot.send_message(chat_id, "❌ Cannot access this URL or content unavailable")
            send_welcome_by_id(chat_id)
            return
        
        # Determine download type
        if media_type == 'audio':
            action_msg = "🎵 Extracting audio..."
            download_type = 'audio'
        elif is_fast:
            action_msg = "⚡ Fast download starting..."
            download_type = 'video'
        else:
            action_msg = "📥 Download starting..."
            download_type = 'video'
        
        bot.send_message(chat_id, action_msg)
        bot.send_chat_action(chat_id, 'upload_video' if media_type != 'audio' else 'upload_audio')
        
        # Download media
        info, file_path = download_media(url, chat_id, download_type, is_fast)
        
        if info and file_path and os.path.exists(file_path):
            file_size = get_file_size(file_path)
            title = clean_filename(info.get('title', 'Unknown'))
            caption = f"✅ Download Complete!\n🎬 {title}\n📊 Size: {file_size}"
            
            if media_type == 'audio' and not FFMPEG_AVAILABLE:
                caption += "\n⚠️ Original format (FFmpeg not available)"
            
            bot.send_message(chat_id, "📤 Uploading file...")
            
            try:
                if media_type == 'audio':
                    with open(file_path, 'rb') as audio_file:
                        if file_path.endswith(('.m4a', '.webm', '.opus')):
                            bot.send_document(chat_id, audio_file, caption=caption, timeout=120)
                        else:
                            bot.send_audio(chat_id, audio_file, caption=caption, timeout=120, title=title[:64])
                else:
                    with open(file_path, 'rb') as video_file:
                        bot.send_video(chat_id, video_file, caption=caption, timeout=120, supports_streaming=True)
                        
            except Exception as send_error:
                logger.error(f"Upload error: {send_error}")
                # Fallback: send as document
                try:
                    with open(file_path, 'rb') as doc_file:
                        bot.send_document(chat_id, doc_file, caption=caption, timeout=120)
                except Exception as doc_error:
                    logger.error(f"Document upload error: {doc_error}")
                    bot.send_message(chat_id, f"❌ Upload failed: {str(send_error)[:100]}")
            
            # Cleanup downloaded file
            try:
                os.unlink(file_path)
                logger.info(f"Cleaned up: {file_path}")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                
        else:
            bot.send_message(chat_id, "❌ Download failed - no content received")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download processing error: {error_msg}")
        
        # User-friendly error messages
        error_messages = {
            "Private video": "❌ Private video - cannot access",
            "Video unavailable": "❌ Video unavailable or deleted",
            "Sign in": "❌ Content requires login",
            "HTTP Error 403": "❌ Access blocked from this site",
            "Unsupported URL": "❌ Unsupported platform or URL",
            "No video formats": "❌ No playable format found",
            "This video is unavailable": "❌ Video not available in your region",
            "Unable to download webpage": "❌ Cannot access this URL",
            "Video unavailable": "❌ Video is no longer available"
        }
        
        for key, message in error_messages.items():
            if key in error_msg:
                bot.send_message(chat_id, message)
                break
        else:
            # Generic error message
            error_display = str(e)[:150]
            bot.send_message(chat_id, f"❌ Error: {error_display}")
    
    finally:
        send_welcome_by_id(chat_id)

# ========== Main Menu System ==========
@bot.message_handler(commands=['start', 'help', 'menu'])
def send_welcome(message):
    user_states[message.chat.id] = 'main'
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🔄 Convert Formats')
    btn2 = types.KeyboardButton('📥 Normal Download')
    btn3 = types.KeyboardButton('⚡ Fast Download')
    btn4 = types.KeyboardButton('🎵 Audio Download')
    btn5 = types.KeyboardButton('🔍 Search Song')
    btn6 = types.KeyboardButton('ℹ️ Help & Info')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    ffmpeg_status = "✅ Available" if FFMPEG_AVAILABLE else "❌ Not installed"
    
    welcome_text = f"""
 **Welcome to MasTer DCS Pro!**

 **Available Features:**

🔄 Convert Formats - Image/Video conversion tools
📥 Normal Download - High quality (720p) 
⚡ Fast Download - Lower quality (360p) for speed
🎵 Audio Download - Extract audio from videos
🔍 Search Song - Find music by lyrics

📋 **Supported Platforms:**
YouTube, Instagram, Facebook, TikTok, Twitter,
Reddit, SoundCloud, Spotify, Vimeo, Twitch & more!

**Choose your desired function below!**
    """
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')

def send_welcome_by_id(chat_id):
    """Send welcome message using chat_id only"""
    try:
        user_states[chat_id] = 'main'
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn1 = types.KeyboardButton('🔄 Convert Formats')
        btn2 = types.KeyboardButton('📥 Normal Download')
        btn3 = types.KeyboardButton('⚡ Fast Download')
        btn4 = types.KeyboardButton('🎵 Audio Download')
        btn5 = types.KeyboardButton('🔍 Search Song')
        btn6 = types.KeyboardButton('ℹ️ Help & Info')
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
        
        bot.send_message(chat_id, "🎛️ Choose your next action:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Welcome message error: {e}")

# ========== Download Handlers ==========
@bot.message_handler(func=lambda message: message.text in ['📥 Normal Download', '⚡ Fast Download', '🎵 Audio Download'])
def handle_download_request(message):
    chat_id = message.chat.id
    
    download_type = {
        '📥 Normal Download': 'normal',
        '⚡ Fast Download': 'fast', 
        '🎵 Audio Download': 'audio'
    }[message.text]
    
    user_states[chat_id] = f'waiting_url_{download_type}'
    
    type_names = {
        'normal': 'Normal Quality 🎥',
        'fast': 'Fast Download ⚡', 
        'audio': 'Audio Only 🎵'
    }
    
    # Additional info based on type
    extra_info = ""
    if download_type == 'audio' and not FFMPEG_AVAILABLE:
        extra_info = "\n\n⚠️ **Note:** FFmpeg not available - downloading in original audio format"
    
    platforms_list = "\n\n📋 **Supported:** YouTube, Instagram, Facebook, TikTok, Twitter, Reddit, SoundCloud, Spotify, Vimeo, Twitch, Dailymotion"
    
    bot.send_message(chat_id, 
                   f"**{type_names[download_type]}**\n\nPlease send the video URL:{extra_info}{platforms_list}",
                   reply_markup=types.ReplyKeyboardRemove(),
                   parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, '').startswith('waiting_url_'))
def handle_url_input(message):
    chat_id = message.chat.id
    url = message.text.strip()
    
    current_state = user_states.get(chat_id, '')
    if not current_state.startswith('waiting_url_'):
        return
        
    download_type = current_state.replace('waiting_url_', '')
    is_fast = download_type == 'fast'
    media_type = 'audio' if download_type == 'audio' else 'video'
    
    user_states[chat_id] = 'processing'
    
    # Start download in separate thread
    thread = threading.Thread(target=process_download, args=(chat_id, url, media_type, is_fast))
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 Starting download process...")

# ========== Format Conversion System ==========
@bot.message_handler(func=lambda message: message.text == '🔄 Convert Formats')
def handle_convert(message):
    user_states[message.chat.id] = 'convert'
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('📷 Image to PDF')
    btn2 = types.KeyboardButton('🎵 Video to MP3')
    btn3 = types.KeyboardButton('🖼️ Image to JPG')
    btn_back = types.KeyboardButton('🔙 Main Menu')
    markup.add(btn1, btn2, btn3, btn_back)
    
    ffmpeg_info = ""
    if not FFMPEG_AVAILABLE:
        ffmpeg_info = "\n\n⚠️ **Video to MP3 requires FFmpeg** (see /ffmpeg_help)"
    
    bot.send_message(message.chat.id, f"**Format Conversion Tools**{ffmpeg_info}", 
                   reply_markup=markup, parse_mode='Markdown')

# Image to PDF Conversion
@bot.message_handler(func=lambda message: message.text == '📷 Image to PDF')
def handle_image_to_pdf(message):
    user_states[message.chat.id] = 'waiting_image_pdf'
    bot.send_message(message.chat.id, "📤 Please send the image you want to convert to PDF", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.chat.id) == 'waiting_image_pdf')
def process_image_to_pdf(message):
    try:
        bot.send_message(message.chat.id, "⏳ Processing your image...")
        
        # Get highest quality photo
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Save temporary image
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg', dir=TEMP_DIR) as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name
        
        pdf_path = None
        try:
            # Open and process image
            image = Image.open(temp_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Create PDF
            pdf_path = temp_path.replace('.jpg', '.pdf')
            image.save(pdf_path, "PDF", resolution=100.0, quality=95)
            
            file_size = get_file_size(pdf_path)
            
            # Send PDF to user
            with open(pdf_path, 'rb') as pdf_file:
                bot.send_document(message.chat.id, pdf_file, 
                                caption=f"✅ Successfully converted to PDF!\n📊 File size: {file_size}")
            
        except Exception as e:
            logger.error(f"PDF conversion error: {e}")
            bot.send_message(message.chat.id, f"❌ Conversion failed: {str(e)}")
        
        finally:
            # Cleanup temporary files
            for path in [temp_path, pdf_path]:
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except Exception as e:
                    logger.error(f"Cleanup error {path}: {e}")
        
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        bot.send_message(message.chat.id, f"❌ Processing error: {str(e)}")
    
    finally:
        send_welcome_by_id(message.chat.id)

# Video to MP3 Conversion
@bot.message_handler(func=lambda message: message.text == '🎵 Video to MP3')
def handle_video_to_mp3(message):
    if not FFMPEG_AVAILABLE:
        bot.send_message(message.chat.id,
                       "❌ **FFmpeg Required**\n\n"
                       "This feature needs FFmpeg installed:\n"
                       "1. Download from: https://ffmpeg.org/\n"
                       "2. Add to system PATH\n"
                       "3. Restart the bot\n\n"
                       "💡 **Quick fix:** Use '🎵 Audio Download' for direct audio extraction",
                       parse_mode='Markdown')
        return
    
    user_states[message.chat.id] = 'waiting_video_mp3'
    bot.send_message(message.chat.id, "🎬 Send the video file to extract audio from (max 50MB)", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['video'], func=lambda message: user_states.get(message.chat.id) == 'waiting_video_mp3')
def process_video_to_mp3(message):
    try:
        # Check file size
        if message.video.file_size > 50 * 1024 * 1024:
            bot.send_message(message.chat.id, "❌ File too large! Maximum size is 50MB")
            send_welcome_by_id(message.chat.id)
            return
            
        bot.send_message(message.chat.id, "⏳ Extracting audio from video...")
        
        # Download video file
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        video_path = os.path.join(TEMP_DIR, f"video_{message.message_id}.mp4")
        with open(video_path, 'wb') as f:
            f.write(downloaded_file)
        
        audio_path = None
        try:
            # Convert video to MP3 using FFmpeg
            audio_path = os.path.join(TEMP_DIR, f"audio_{message.message_id}.mp3")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'libmp3lame',
                '-ab', '192k',  # Audio bitrate
                '-ar', '44100',  # Sample rate
                '-y',  # Overwrite output
                audio_path
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(audio_path):
                file_size = get_file_size(audio_path)
                
                # Send MP3 to user
                with open(audio_path, 'rb') as audio_file:
                    bot.send_audio(message.chat.id, audio_file, 
                                 caption=f"✅ Audio extracted successfully!\n📊 Size: {file_size}")
            else:
                error_msg = result.stderr[:200] if result.stderr else "Conversion failed"
                bot.send_message(message.chat.id, f"❌ Extraction failed: {error_msg}")
                
        except subprocess.TimeoutExpired:
            bot.send_message(message.chat.id, "❌ Conversion timeout - file may be too large")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"MP3 extraction error: {error_msg}")
            
            if "ffprobe" in error_msg.lower() or "ffmpeg" in error_msg.lower():
                bot.send_message(message.chat.id, 
                               "❌ FFmpeg error!\n\n"
                               "Please check:\n"
                               "• FFmpeg installation\n"
                               "• System PATH configuration\n"
                               "• Bot restart after installation")
            else:
                bot.send_message(message.chat.id, f"❌ Conversion error: {str(e)[:100]}")
        
        finally:
            # Cleanup files
            for path in [video_path, audio_path]:
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
        
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        bot.send_message(message.chat.id, f"❌ Processing error: {str(e)}")
    
    finally:
        send_welcome_by_id(message.chat.id)

# Image to JPG Conversion
@bot.message_handler(func=lambda message: message.text == '🖼️ Image to JPG')
def handle_image_to_jpg(message):
    user_states[message.chat.id] = 'waiting_image_jpg'
    bot.send_message(message.chat.id, "📤 Send the image to convert to JPG format", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.chat.id) == 'waiting_image_jpg')
def process_image_to_jpg(message):
    try:
        bot.send_message(message.chat.id, "⏳ Converting image to JPG...")
        
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.temp', dir=TEMP_DIR) as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name
        
        jpg_path = None
        try:
            # Convert to JPG
            image = Image.open(temp_path)
            image = image.convert('RGB')
            
            jpg_path = os.path.join(TEMP_DIR, f"converted_{message.message_id}.jpg")
            image.save(jpg_path, "JPEG", quality=95, optimize=True)
            
            file_size = get_file_size(jpg_path)
            
            # Send converted image
            with open(jpg_path, 'rb') as jpg_file:
                bot.send_photo(message.chat.id, jpg_file, 
                             caption=f"✅ Converted to JPG successfully!\n📊 Size: {file_size}")
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Conversion error: {str(e)}")
        
        finally:
            # Cleanup
            for path in [temp_path, jpg_path]:
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
        
    except Exception as e:
        logger.error(f"JPG conversion error: {e}")
        bot.send_message(message.chat.id, f"❌ Processing error: {str(e)}")
    
    finally:
        send_welcome_by_id(message.chat.id)

# ========== Song Search System - FIXED VERSION ==========
@bot.message_handler(func=lambda message: message.text == '🔍 Search Song')
def handle_lyrics_search(message):
    user_states[message.chat.id] = 'waiting_lyrics'
    bot.send_message(message.chat.id, "🎤 Enter song lyrics or title to search:", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_lyrics')
def search_by_lyrics(message):
    try:
        lyrics = message.text.strip()
        if len(lyrics) < 2:
            bot.send_message(message.chat.id, "❌ Please enter at least 2 characters")
            send_welcome_by_id(message.chat.id)
            return
        
        bot.send_message(message.chat.id, f"🔍 Searching for: '{lyrics}'")
        
        thread = threading.Thread(target=perform_song_search, args=(message.chat.id, lyrics))
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        logger.error(f"Search initialization error: {e}")
        bot.send_message(message.chat.id, "❌ Search failed. Please try again.")
        send_welcome_by_id(message.chat.id)

def perform_song_search(chat_id, lyrics):
    """Perform song search in background thread - FIXED VERSION"""
    try:
        # Create search query
        search_query = f"{lyrics} official audio"
        
        bot.send_message(chat_id, "🎵 Searching YouTube...")
        
        # Use simpler yt-dlp options for search
        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'extract_flat': True,  # Use flat extraction for faster search
            'socket_timeout': 15,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search YouTube using ytsearch
            search_url = f"ytsearch10:{search_query}"
            info = ydl.extract_info(search_url, download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                bot.send_message(chat_id, "❌ No results found for your search")
                return
            
            entries = info['entries']
            valid_entries = []
            
            # Process search results
            for entry in entries:
                if entry and entry.get('url'):
                    title = entry.get('title', 'Unknown Title')
                    duration = entry.get('duration')
                    duration_str = format_duration(duration)
                    url = entry.get('url')
                    
                    # Filter out live streams and very long videos
                    if duration and duration > 36000:  # Longer than 10 hours
                        continue
                        
                    valid_entries.append({
                        'title': title,
                        'url': url,
                        'duration': duration_str
                    })
            
            if not valid_entries:
                bot.send_message(chat_id, "❌ No valid results found")
                return
            
            # Show top results
            results_text = "🎵 **Top Results:**\n\n"
            for i, entry in enumerate(valid_entries[:5], 1):
                results_text += f"{i}. {entry['title']}\n"
                results_text += f"   ⏱️ {entry['duration']}\n\n"
            
            results_text += "⬇️ Downloading the first result..."
            bot.send_message(chat_id, results_text, parse_mode='Markdown')
            
            # Download the first result
            first_result = valid_entries[0]
            bot.send_message(chat_id, f"🎵 Downloading: {first_result['title']}")
            
            # Use the existing download system
            process_download(chat_id, first_result['url'], 'audio', False)
                
    except Exception as e:
        logger.error(f"Song search error: {e}")
        error_msg = str(e)
        
        # Provide specific error messages
        if "Unable to download webpage" in error_msg:
            bot.send_message(chat_id, "❌ Search service unavailable. Please try again later.")
        elif "No results found" in error_msg:
            bot.send_message(chat_id, "❌ No results found. Try different keywords.")
        else:
            bot.send_message(chat_id, f"❌ Search error: {error_msg[:100]}")
            
    finally:
        send_welcome_by_id(chat_id)

# ========== Additional Commands ==========
@bot.message_handler(func=lambda message: message.text == '🔙 Main Menu')
def handle_back(message):
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help & Info')
def handle_help(message):
    help_text = """
🛠 **MediaBot Pro - Complete Guide**

⚡ **Download Options:**
- 📥 Normal Download: High quality (720p) videos
- ⚡ Fast Download: Lower quality (360p) for speed
- 🎵 Audio Download: Extract audio from any video

🔄 **Conversion Tools:**
- 📷 Image to PDF: Convert images to PDF documents
- 🎵 Video to MP3: Extract audio from video files
- 🖼️ Image to JPG: Convert images to JPG format

🔍 **Music Search:**
- Search by lyrics or song title
- Automatic download of best match

📋 **Supported Platforms:**
- YouTube, Instagram, Facebook, TikTok
- Twitter, Reddit, SoundCloud, Spotify  
- Vimeo, Twitch, Dailymotion, and more!

🔧 **Technical Info:**
- Auto cleanup every hour
- Support for multiple formats
- Professional error handling

💡 **Quick Commands:**
/start - Main menu
/status - System status  
/clean - Clean temporary files
/ffmpeg_help - FFmpeg setup guide

🚀 **Ready to use! Choose any option from the main menu.**
    """
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def check_status(message):
    """Display comprehensive system status"""
    chat_id = message.chat.id
    
    ffmpeg_status = "✅ Installed and working" if FFMPEG_AVAILABLE else "❌ Not available"
    
    # Count temporary files
    temp_files = len([f for f in os.listdir(TEMP_DIR) if os.path.isfile(os.path.join(TEMP_DIR, f))])
    
    # Calculate total size
    total_size = 0
    for file in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, file)
        if os.path.isfile(file_path):
            total_size += os.path.getsize(file_path)
    size_mb = total_size / (1024 * 1024)
    
    status_text = f"""
🤖 **System Status Report**

🐍 **Python Version:** {sys.version.split()[0]}
📁 **Temporary Files:** {temp_files} files
💾 **Storage Usage:** {size_mb:.2f} MB
🔧 **FFmpeg Status:** {ffmpeg_status}
👥 **Active Sessions:** {len(user_states)}
🧹 **Auto Cleanup:** ✅ Active (hourly)

🔄 **All Systems:** ✅ Operational
💡 **Status:** 🟢 Running optimally
"""
    
    bot.send_message(chat_id, status_text, parse_mode='Markdown')

@bot.message_handler(commands=['clean'])
def clean_temp(message):
    """Immediate cleanup command"""
    deleted_files = auto_cleanup.cleanup_temp_files(max_age_minutes=0)
    if deleted_files > 0:
        bot.send_message(message.chat.id, f"🧹 Cleaned {deleted_files} temporary files!")
    else:
        bot.send_message(message.chat.id, "✅ No temporary files to clean")

@bot.message_handler(commands=['ffmpeg_help'])
def ffmpeg_help(message):
    """FFmpeg installation guide"""
    help_text = """
🔧 **FFmpeg Installation Guide**

📥 **Download FFmpeg:**
1. Visit: https://www.gyan.dev/ffmpeg/builds/
2. Download: `ffmpeg-release-full.7z` (latest version)

🛠 **Installation Steps:**

**Windows:**
1. Extract the downloaded file
2. Copy the folder to `C:\\ffmpeg\\`
3. Press `Win + R`, type `sysdm.cpl`
4. Click "Environment Variables"
5. Under "System Variables", find "Path", click "Edit"
6. Click "New", add: `C:\\ffmpeg\\bin`
7. Click "OK" to save

**Verification:**
1. Open Command Prompt
2. Type: `ffmpeg -version`
3. If you see version info, installation is successful

🔄 **After installation, restart this bot.**

💡 **Note:** FFmpeg enables audio conversion and better format support.
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Handle unknown commands"""
    if message.chat.id not in user_states:
        send_welcome(message)
    else:
        bot.send_message(message.chat.id, 
                        "❌ Command not recognized\n\n"
                        "Please use the menu buttons or /help for assistance")
def is_running_on_heroku():
    return 'DYNO' in os.environ

if is_running_on_heroku():
    # إعدادات خاصة بـ Heroku
    TEMP_DIR = "/tmp/temp_files"
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    # استخدام متغير البيئة للتوكن
    API_TOKEN = os.environ.get('BOT_TOKEN', '8526634581:AAHBOfZw1UlBwrao1Wf2nY4TRGCGpKnce4g')
    
    # تعديل إعدادات التسجيل
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🚀 Running on Heroku...")
# ========== Main Execution ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MediaBot Pro - Starting System")
    print("=" * 60)
    
    # Initial cleanup
    initial_cleanup = auto_cleanup.cleanup_temp_files()
    if initial_cleanup > 0:
        print(f"🧹 Initial cleanup: {initial_cleanup} files removed")
    
    # Start auto cleanup system
    auto_cleanup.start_auto_cleanup()
    
    try:
        # Get bot info
        bot_info = bot.get_me()
        print(f"✅ Bot initialized: @{bot_info.username}")
        print(f"🐍 Python version: {sys.version.split()[0]}")
        print(f"🔧 FFmpeg status: {'✅ Available' if FFMPEG_AVAILABLE else '❌ Not available'}")
        print("🧹 Auto cleanup: ✅ Active (hourly)")
        print("📊 System ready for requests...")
        print("=" * 60)
        
        # Start polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Bot crashed: {e}")
    finally:
        print("🛑 Shutting down bot...")
        auto_cleanup.stop_auto_cleanup()
        final_cleanup = auto_cleanup.cleanup_temp_files()
        if final_cleanup > 0:
            print(f"🧹 Final cleanup: {final_cleanup} files removed")
        print("✅ Bot stopped successfully")