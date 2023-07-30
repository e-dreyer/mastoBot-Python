import logging

__all__ = ["mastoBot", "configManager"]

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)-25s - [%(levelname)s] - %(module)s.%(funcName)-30s - %(message)-50s",
)

# File logger
file_logger = logging.FileHandler("scraper.log", "w")
file_logger.setLevel(logging.INFO)
file_logger.setFormatter(
    logging.Formatter(
        "%(asctime)-25s - [%(levelname)s] - %(module)s.%(funcName)-30s - %(message)-50s"
    )
)

# Get the root logger
root_logger = logging.getLogger()
root_logger.addHandler(file_logger)