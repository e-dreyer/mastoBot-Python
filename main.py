from typing import List, Dict, AnyStr
import logging
import re
import hashlib
from bs4 import BeautifulSoup

import asyncio
import aiohttp
import time

from mastoBot.configManager import ConfigAccessor
from mastoBot.mastoBot import MastoBot, handleMastodonExceptions

def generate_redis_key(input_string: AnyStr) -> AnyStr:
    # Create a SHA-256 hash object
    sha256_hash = hashlib.sha256()

    # Convert the input string to bytes (required for hashing)
    input_bytes = input_string.encode("utf-8")

    # Update the hash object with the input bytes
    sha256_hash.update(input_bytes)

    # Get the hexadecimal representation of the hash (fixed-length)
    hash_hex = sha256_hash.hexdigest()

    return hash_hex

def toPascalCase(s: AnyStr) -> AnyStr:
    parts = s.split(" ")
    return parts[0].capitalize() + "".join(part.title() for part in parts[1:])

def shortenTopicUrl(url: AnyStr) -> AnyStr:
    return re.sub(r"/t/[^/]+/", "/t/", url)


class MyBot(MastoBot):
    @handleMastodonExceptions
    def processMention(self, mention: Dict):
        api_status = self.getStatus(mention.get("status"))
        api_account = self.getAccount(mention.get("account"))
        content = api_status.get("content")

        # Check for report tag
        report_pattern = r"(.*?)(?<!\S)\$report\b\s*(.*)</p>"
        report_match = re.search(report_pattern, content)

        # If report message
        if report_match:
            before_report = report_match.group(1).strip()
            report_message = report_match.group(2).strip()
            logging.info(f"⛔ \t Report message received: {report_message}")

            template_data = {
                "creator": api_account.get("acct"),
                "reported_post_id": mention.get("status"),
                "reported_post_url": api_status.get("url"),
                "report_message": report_message,
            }

            try:
                output = self.getTemplate("report.txt", template_data)
                self._api.status_post(status=output, visibility="direct")
            except Exception as e:
                logging.critical("❗ \t Error posting status message")
                raise e
        else:
            # Check boost and favourite configs
            shouldReblog = self.shouldReblog(mention.get("status"))
            shouldFavourite = self.shouldFavorite(mention.get("status"))
            altTextTestPassed = self.altTextTestPassed(mention.get("status"), "boosts")

            # Check boost
            if shouldReblog:
                try:
                    self.reblogStatus(mention.get("status"))
                except Exception as e:
                    logging.warning(f"❗ \t Status could not be boosted")
                    logging.error(e)
            elif not altTextTestPassed:
                template_data = {"account": api_account.get("acct")}

                try:
                    output = self.getTemplate("missing_alt_text.txt", template_data)
                    self._api.status_post(status=output, visibility="direct")
                except Exception as e:
                    logging.critical("❗ \t Error sending missing-alt-text message")
                    raise e

            # Check favourite
            if shouldFavourite:
                try:
                    self.favoriteStatus(mention.get("status"))
                except Exception as e:
                    logging.warning(f"❗ \t Status could not be favourited")
                    logging.error(e)

        logging.info(f"📬 \t Mention processed: {mention.get('id')}")
        self.dismissNotification(mention.get("id"))

    @handleMastodonExceptions
    def processReblog(self, reblog: Dict):
        self.dismissNotification(reblog.get("id"))

    @handleMastodonExceptions
    def processFavourite(self, favourite: Dict):
        self.dismissNotification(favourite.get("id"))

    @handleMastodonExceptions
    def processFollow(self, follow: Dict):
        # Get latest account from the Mastodon API
        api_account = self.getAccount(follow.get("account"))
        account = api_account.get("acct")

        template_data = {"account": account}

        # Generate the welcoming message from the template
        try:
            output = self.getTemplate("new_follow.txt", template_data)
            self._api.status_post(status=output, visibility="direct")
        except Exception as e:
            logging.critical("❗ \t Error posting Status")
            raise e

        logging.info(f"📭 \t Follow processed: {follow.get('id')}")
        self.dismissNotification(follow.get("id"))

    @handleMastodonExceptions
    def processPoll(self, poll: Dict):
        self.dismissNotification(poll.get("id"))

    @handleMastodonExceptions
    def processFollowRequest(self, follow_request: Dict):
        self.dismissNotification(follow_request.get("id"))

    @handleMastodonExceptions
    def processUpdate(self, update: Dict) -> None:
        self.dismissNotification(update.get("id"))

    async def fetchLatestPosts(self) -> List[AnyStr]:
        posts: List[AnyStr] = list()
        url = "https://discuss.python.org/latest"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    # Get the page soup
                    soup = BeautifulSoup(await response.text(), "html.parser")

                    # Get topics soup
                    topics_soup = soup.find_all("tr", class_="topic-list-item")

                    # Loop through topics
                    for topic_soup in topics_soup:
                        # Get URL
                        topic_url = topic_soup.find(
                            "a", class_="title raw-link raw-topic-link"
                        ).get("href")

                        # Get page data
                        post_data = await self.getPostDataFromUrl(session, topic_url)

                        # If the record does not already exist
                        if not self.localStoreExists(
                            "python-discuss-post", post_data.get("id")
                        ):
                            self.localStoreSet(
                                "pending-python-discuss-post",
                                post_data.get("id"),
                                post_data,
                            )
                        else:
                            self.localStoreSet(
                                "python-discuss-post", post_data.get("id"), post_data
                            )
                else:
                    logging.warning(
                        "Failed to retrieve the page. Status Code:", response.status
                    )

    async def getPostDataFromUrl(self, session, url: str) -> Dict:
        async with session.get(url) as response:
            if response.status == 200:
                # Get the page soup
                soup = BeautifulSoup(await response.text(), "html.parser")

                # Get the topic soup
                topic_soup = soup.find("div", {"id": "topic-title"})

                # Get the topic attributes
                topic_title = topic_soup.find("a").text.strip()
                topic_category = topic_soup.find(
                    "span", class_="category-name"
                ).text.strip()

                # Generate an ID from the shortened URL
                shortened_link = shortenTopicUrl(url)
                generated_id = generate_redis_key(shortened_link)

                post = {
                    "id": generated_id,
                    "title": topic_title,
                    "url": shortened_link,
                    "topic_category": toPascalCase(topic_category),
                }

                return post
            else:
                logging.warning(
                    "Failed to retrieve the page. Status Code:", response.status
                )

    async def processPythonDiscussPendingPosts(self) -> None:
        for record_id in self.r.scan_iter(match="pending-python-discuss-post:*"):
            key, id = record_id.split(":")
            record = self.localStoreGet(key, id)
            output = self.getTemplate("discuss_post.txt", record)

            try:
                new_status = self._api.status_post(status=output, visibility="unlisted")

                record.setdefault("status_url", new_status.get("url"))
                record.setdefault("status_uri", new_status.get("uri"))
                record.setdefault("status_id", new_status.get("id"))

                logging.info(f"✨ \t New python-discuss posted: {new_status.get('url')}")

                self.localStoreDelete(key, id)
                self.localStoreSet("python-discuss-post", id, record)

            except Exception as e:
                logging.critical("❗ \t Error posting Status")
                raise e
            
            await asyncio.sleep(120)


if __name__ == "__main__":
    config = ConfigAccessor("config.yml")
    credentials = ConfigAccessor("credentials.yml")
    bot = MyBot(credentials=credentials, config=config)

    async def runBot():
        while True:
            logging.info("✅ \t Running bot")
            await bot.run()
            await asyncio.sleep(10)

    async def runScraper():
        while True:
            logging.info("⛏️ \t Running scraper")
            await bot.fetchLatestPosts()
            await bot.processPythonDiscussPendingPosts()
            await asyncio.sleep(120) 

    async def main():
        await asyncio.gather(runBot(), runScraper())

    while True:
        try:
            asyncio.run(main())
        except:
            time.sleep(10)
            pass
