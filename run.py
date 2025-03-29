import subprocess
import sys
import os
import signal
import asyncio
import logging
import multiprocessing
import queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Configuration of logging for the entire project
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler('app.log', encoding='utf-8')  # Write to file
    ]
)
logger = logging.getLogger('run_script')

def run_django():
    logger.info("Starting Django server...")
    django_process = subprocess.Popen([sys.executable, 'manage.py', 'runserver'])
    logger.info(f"Django server started (PID: {django_process.pid})")
    return django_process

async def run_bot():
    logger.info("Starting Telegram bot...")
    try:
        from tg_bot.bot import main
        await main()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

def run_telethon_parser(message_queue):
    logger.info("Starting Telethon parser...")
    try:
        from tg_bot.telethon_worker import telethon_worker_process
        telethon_worker_process(message_queue)
    except Exception as e:
        logger.error(f"Error starting Telethon parser: {e}")

def message_processor(message_queue):
    logger.info("Starting message processor...")
    while True:
        try:
            # Get message from queue (if queue is empty, wait)
            message = message_queue.get(block=True, timeout=1)
            logger.debug(f"Received message from queue: {message.get('message_info', {}).get('message_id')}")
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error processing message: {e}")

def run_services():
    start_time = datetime.now()
    logger.info(f"====== Starting services {start_time.strftime('%Y-%m-%d %H:%M:%S')} ======")
    
    # Create a queue for inter-process communication
    message_queue = multiprocessing.Queue()
    
    # Start Telethon parser in a separate process
    telethon_process = multiprocessing.Process(
        target=run_telethon_parser,
        args=(message_queue,)
    )
    telethon_process.daemon = True
    telethon_process.start()
    logger.info(f"Telethon parser process started (PID: {telethon_process.pid})")
    
    # Start message processor in a separate process
    processor_process = multiprocessing.Process(
        target=message_processor,
        args=(message_queue,)
    )
    processor_process.daemon = True
    processor_process.start()
    logger.info(f"Message processor process started (PID: {processor_process.pid})")
    
    # Start Django server
    django_process = run_django()
    
    try:
        # Start bot in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logger.info("\nReceived termination signal (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Error executing: {e}")
    finally:
        logger.info("Stopping services...")
        
        # Stop Django server
        django_process.terminate()
        django_process.wait()
        
        # Stop Telethon parser
        telethon_process.terminate()
        telethon_process.join(timeout=5)
        
        # Stop message processor
        processor_process.terminate()
        processor_process.join(timeout=5)
        
        end_time = datetime.now()
        runtime = end_time - start_time
        
        logger.info(f"Services stopped. Runtime: {runtime}")
        logger.info("====== End ======")

if __name__ == "__main__":
    # Set the limit on the number of open files for Windows
    if sys.platform.startswith('win'):
        try:
            import win32file
            win32file._setmaxstdio(2048)
        except:
            pass
    
    run_services() 