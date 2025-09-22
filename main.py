import sys
from core.app_logger import logger
from ui.floating_icon import FloatingIcon


def main():
    floating_icon = None
    try:
        logger.info("Assistant starting...")
        floating_icon = FloatingIcon()
        logger.info("Assistant ready - click the floating icon to give voice commands")
        floating_icon.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.exception(f"Application failed to start: {e}")        
        sys.exit(1)
    finally:
        if floating_icon:
            floating_icon.quit_app()
        logger.info("Application shutdown complete")

# Config toggle
if __name__ == "__main__":     # only create console in debug/logging mode
    main()