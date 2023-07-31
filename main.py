from typing import List, Dict, AnyStr
from jinja2 import Environment, FileSystemLoader
import logging
import re
import hashlib
from bs4 import BeautifulSoup

import asyncio
import aiohttp

from mastoBot.configManager import ConfigAccessor
from mastoBot.mastoBot import MastoBot, handleMastodonExceptions

def generate_redis_key(input_string: AnyStr) -> AnyStr:
    # Create a SHA-256 hash object
    sha256_hash = hashlib.sha256()

    # Convert the input string to bytes (required for hashing)
    input_bytes = input_string.encode('utf-8')

    # Update the hash object with the input bytes
    sha256_hash.update(input_bytes)

    # Get the hexadecimal representation of the hash (fixed-length)
    hash_hex = sha256_hash.hexdigest()

    return hash_hex

def toPascalCase(s: AnyStr) -> AnyStr:
    parts = s.split(' ')
    return parts[0].capitalize() + ''.join(part.title() for part in parts[1:])

def shortenTopicUrl(url: AnyStr) -> AnyStr:
    return re.sub(r'/t/[^/]+/', '/t/', url)

class MyBot(MastoBot):
    @handleMastodonExceptions
    def processMention(self, mention: Dict):
        # Get the content from the mention
        content = self.getStatus(mention.get("status")).get("content")

        # Check for report tag
        report_pattern = r"(.*?)(?<!\S)\$report\b\s*(.*)</p>"
        report_match = re.search(report_pattern, content)
        if report_match:
            before_report = report_match.group(1).strip()
            report_message = report_match.group(2).strip()
            logging.info(f"⛔ \t Report message received: {report_message}")

            # Get account
            api_account = self.getAccount(mention.get("account"))
            api_status = self.getStatus(mention.get("status"))

            try:
                file_loader = FileSystemLoader("templates")
                env = Environment(loader=file_loader)
                template = env.get_template("report.txt")

                output = template.render(
                    creator=api_account.get("acct"),
                    reported_post_id=mention.get("status"),
                    reported_post_url=api_status.get("url"),
                    report_message=report_message,
                )
            except Exception as e:
                logging.critical("❗ \t Error initializing template")
                raise e

            try:
                self._api.st(status=output, visibility="direct")
            except Exception as e:
                logging.critical("❗ \t Error posting status message")
                raise e
        else:
            # Perform actions after calling the original function
            if self.shouldReblog(mention.get("status")):
                try:
                    self.reblogStatus(mention.get("status"))
                except Exception as e:
                    logging.warning(
                        f"❗ \t Status could not be boosted: {mention.get('status')}"
                    )
                    logging.error(e)

            if self.shouldFavorite(mention.get("status")):
                try:
                    self.favoriteStatus(mention.get("status"))
                except Exception as e:
                    logging.warning(
                        f"❗ \t Status could not be favourited: {mention.get('status')}"
                    )
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

        try:
            file_loader = FileSystemLoader("templates")
            env = Environment(loader=file_loader)
            template = env.get_template("new_follow.txt")
            output = template.render(account=account)
        except Exception as e:
            logging.critical("❗ \t Error initializing template")
            raise e

        # Generate the welcoming message from the template
        try:
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

    @handleMastodonExceptions
    def shouldReblog(self, status_id: int) -> bool:
        isParentStatus = self.isParentStatus(status_id)
        isByFollower = self.isByFollower(status_id)
        boostConfig = self.config.get("boosts")

        if isParentStatus and boostConfig.get("parents"):
            if boostConfig.get("followers_only"):
                return isByFollower
            else:
                return True
        elif not isParentStatus and boostConfig.get("children"):
            if boostConfig.get("followers_only"):
                return isByFollower
            else:
                return True

    @handleMastodonExceptions
    def shouldFavorite(self, status_id: int) -> bool:
        isParentStatus = self.isParentStatus(status_id)
        isByFollower = self.isByFollower(status_id)
        favoriteConfig = self.config.get("favorites")

        if isParentStatus and favoriteConfig.get("parents"):
            if favoriteConfig.get("followers_only"):
                return isByFollower
            else:
                return True
        elif not isParentStatus and favoriteConfig.get("children"):
            if favoriteConfig.get("followers_only"):
                return isByFollower
            else:
                return True
            
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
                        topic_url = topic_soup.find("a", class_="title raw-link raw-topic-link").get("href")
                        
                        # Get page data
                        post_data = await self.getPostDataFromUrl(session, topic_url)
                        
                        # If the record does not already exist
                        if not self.localStoreExists("python-discuss-post", post_data.get('id')):
                            self.localStoreSet("pending-python-discuss-post", post_data.get('id'), post_data)
                        else:
                            self.localStoreSet("python-discuss-post", post_data.get('id'), post_data)
                else:
                    logging.warning("Failed to retrieve the page. Status Code:", response.status)

    async def getPostDataFromUrl(self, session, url: str) -> Dict:
        async with session.get(url) as response:
            if response.status == 200:
                # Get the page soup
                soup = BeautifulSoup(await response.text(), "html.parser")
                
                # Get the topic soup
                topic_soup = soup.find("div", {"id": "topic-title"})
                
                # Get the topic attributes
                topic_title = topic_soup.find("a").text.strip()
                topic_category = topic_soup.find("span", class_="category-name").text.strip()
                
                # Generate an ID from the URL
                generated_id = generate_redis_key(url)
                
                post = {
                    "id": generated_id,
                    "title": topic_title,
                    "url": shortenTopicUrl(url),
                    "topic_category": toPascalCase(topic_category)
                }
                
                return post
            else:
                logging.warning("Failed to retrieve the page. Status Code:", response.status)

    def processPythonDiscussPendingPosts(self) -> None:
        for record_id in self.r.scan_iter(match="pending-python-discuss-post:*"):
            key, id = record_id.split(":")
            record = self.localStoreGet(key, id)
            output = self.getTemplate("discuss_post.txt", record)
            
            try:
                new_status = self._api.status_post(status=output, visibility="unlisted")
                
                record.setdefault("status_url", new_status.get('url'))
                record.setdefault("status_uri", new_status.get('uri'))
                record.setdefault("status_id", new_status.get('id'))
                
                logging.info(f"✨ \t New python-discuss posted: {new_status.get('url')}")
                
                self.localStoreDelete(key, id)
                self.localStoreSet("python-discuss-post", id, record)
                
            except Exception as e:
                logging.critical("❗ \t Error posting Status")
                raise e
    
if __name__ == "__main__":
    
    config = ConfigAccessor("config.yml")
    credentials = ConfigAccessor("credentials.yml")
    bot = MyBot(credentials=credentials, config=config)
    
    async def runBot():
        while True:
            logging.info("✅ \t Running bot")
            loop = asyncio.get_event_loop()
            await asyncio.gather(
                loop.run_in_executor(None, bot.run),
            )
            await asyncio.sleep(10)

    async def runScraper():
        while True:
            logging.info("⛏️ \t Running scraper")
            await asyncio.gather(bot.fetchLatestPosts())
            
            loop = asyncio.get_event_loop()
            await asyncio.gather(
                loop.run_in_executor(None, bot.processPythonDiscussPendingPosts)
            )
            await asyncio.sleep(120)
            
    async def main():
        await asyncio.gather(runBot(), runScraper())
        
    asyncio.run(main())