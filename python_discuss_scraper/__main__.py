from typing import List, Dict, AnyStr, Any
from jinja2 import Environment, FileSystemLoader
import logging
import re
import time
import hashlib
import requests
from bs4 import BeautifulSoup

import asyncio
import aiohttp

def to_camel_case(s):
    parts = s.split(' ')
    return '#' + parts[0].capitalize() + ''.join(part.title() for part in parts[1:])

def shortenTopicUrl(url: AnyStr) -> AnyStr:
    return re.sub(r'/t/[^/]+/', '/t/', url)

async def fetchCategories() -> List[Any]:
    categories: List[Any] = list()
    
    async with aiohttp.ClientSession() as session:
        url = "https://discuss.python.org/categories"
        async with session.get(url) as response:
            if response.status == 200:
                # Get page
                soup = BeautifulSoup(await response.text(), "html.parser")
                
                categories_soup = soup.find_all('td', class_= "category")
                
                for category_soup in categories_soup:
                    category_title = category_soup.find("span").text.strip()
                    category_url = "https://discuss.python.org" + category_soup.find("a")["href"]
                    category_hashtag = to_camel_case(category_title)
                    
                    new_category = {
                        "title": category_title,
                        "url": category_url,
                        "hashtag": category_hashtag
                    }
                    
                    categories.append(new_category)
        
    return categories

async def fetchTags() -> List[Any]:
    tags: List[Any] = list()
    
    async with aiohttp.ClientSession() as session:
        url = "https://discuss.python.org/tags"
        async with session.get(url) as response:
            if response.status == 200:
                # Get page
                soup = BeautifulSoup(await response.text(), "html.parser")
                
                tags_soup = soup.find_all('div', class_= "tag-box")
                
                for tag_soup in tags_soup:
                    tag_title = tag_soup.find("a").text.strip()
                    tag_url = tag_soup.find("a")["href"]
                    tag_hashtag = to_camel_case(tag_title)
                    
                    new_tag = {
                        "title": tag_title,
                        "url": tag_url,
                        "hashtag": tag_hashtag
                    }
                    
                    tags.append(new_tag)
        
    return tags

async def fetchLatest() -> List[AnyStr]:
    latest: List[Any] = list()
    
    async with aiohttp.ClientSession() as session:
        url = "https://discuss.python.org/latest"
        
        async with session.get(url) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), "html.parser")
                
                # Get all of the topics
                topics_soup = soup.find_all("tr", class_="topic-list-item")
                for topic_soup in topics_soup:
                    short_url = shortenTopicUrl(topic_soup.find("a", class_="title")["href"])
                    latest.append(short_url)
                    
    return latest
                    
async def main() -> None:
    categories = await fetchCategories()
    tags = await fetchTags()
    latest = await fetchLatest()
    return categories, tags, latest

if __name__ == "__main__":
    categories, tags, latest = asyncio.run(main())
    
    # print(categories)
    # print(tags)
    print(latest)