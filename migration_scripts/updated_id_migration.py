import re

import json

import asyncio
import aiohttp #type: ignore

import time

from mastoBot.configManager import ConfigAccessor
from mastoBot.mastoBot import MastoBot, handleMastodonExceptions
from redis.commands.json.path import Path

from main import generate_redis_key, shortenTopicUrl, toPascalCase, MyBot

config = ConfigAccessor("config_local.yml")
credentials = ConfigAccessor("credentials.yml")

bot = MyBot(credentials=credentials, config=config)
bot_id = bot.getMe().get('id')
    
async def generatePostFiles():
    
    url_pattern = r"URL: <a href=\"(.*?)\" target=\"_blank\" rel=\"nofollow noopener noreferrer\">"

    posts = bot.getAccountStatuses()
    
    posts_to_update = list()
    
    posts_to_delete = list()
    
    async with aiohttp.ClientSession() as session:
        for post in posts:

            post_content = post.get('content')
                    
            url = re.findall(url_pattern, post_content)
            
            if url:
                page_data = await bot.getPostDataFromUrl(session, url[0])
                
                if page_data:
                    new_discussion_post = {
                        **page_data,
                        'mastodon_id': post.get('id'),
                        'mastodon_url': post.get('url'),
                    }
                    
                    posts_to_update.append(new_discussion_post)
                    print(new_discussion_post)
                    print()
                else:
                    post_to_delete = {
                                'mastodon_id': post.get('id'),
                                'mastodon_url': post.get('url'),
                                'id': generate_redis_key(url[0]),
                            }
                    
                    posts_to_delete.append(post_to_delete)
                    print(post_to_delete)
                    print()
                
    posts_to_update_json = {'posts': posts_to_update}
    posts_to_delete_json = {'posts': posts_to_delete}
    
    file_path = "posts_to_update.json"

    # Open the file in write mode
    with open(file_path, "w") as json_file:
        # Write the JSON object to the file
        json.dump(posts_to_update_json, json_file, indent=4)
        
    file_path = "posts_to_delete.json"

    # Open the file in write mode
    with open(file_path, "w") as json_file:
        # Write the JSON object to the file
        json.dump(posts_to_delete_json, json_file, indent=4)
        
async def processJsonFiles():
    """
    Process the JSON output files.
    
    This was used to update the Redis store and apply the new template to the existing toots. 
    This needs to be done slowly as it can easily hit the API limit. For 236 posts this probably ran
    for about an hour
    """
    
    def getLocalPostWithUrl(url: str, local_posts: dict):
        for local_post in local_posts:
            if local_post.get('url') == url:
                return local_post
        return None
    
    posts_to_update_json, posts_to_delete_json = list(), list()
    
    file_path = "posts_to_update.json"
    with open(file_path, "r") as json_file:
        posts_to_update_json = json.load(json_file)
    
    # Get the local and remote posts
    local_store_posts = bot.localStoreObjectGetAll("python-discuss-post")
    remote_posts_to_update = posts_to_update_json['posts']
    
    for post in remote_posts_to_update:
        # Get local post
        local_post_id = getLocalPostWithUrl(
            url=post['url'], 
            local_posts=local_store_posts
            )
        
        if local_post_id:
            print('local_post found')
            # Delete local post
            bot.localStoreDelete(
                key='python-discuss-post', 
                id=local_post_id
                )
            
            # Create new local post
            bot.localStoreSet(
                key='python-discuss-post',
                id=post['id'],
                data=post
            )
            
            generated_template = bot.getTemplate('discuss_post.txt', {
                'title': post['title'],
                'topic_category': post['topic_category'],
                'url': post['url']
            })
            
            print(generated_template)
            print()
            
            # bot._api.status_update(post['mastodon_id'], generated_template)
            # time.sleep(20)
        
async def purgeOldDatabase():
    """
    Purge the old style records of posts. This is simply done by checking whether the 'mastodon_id' field
    is missing
    """
    local_store_posts = bot.localStoreObjectGetAll("python-discuss-post")
    local_posts_to_delete = list(filter(lambda x: not x.get('mastodon_id'), local_store_posts))
    
    for post_to_delete in local_posts_to_delete:
        bot.localStoreDelete("python-discuss-post", post_to_delete['id'])
    
async def deleteOldPosts():
    """
    Delete old posts from Mastodon, if they are in the posts_to_delete.json file. Normally, these are posts
    which were manually removed by the admin or the URLs on the Python Discuss page is dead
    """
    posts_to_delete_json = list(), list()
        
    file_path = "posts_to_delete.json"
    with open(file_path, "r") as json_file:
        posts_to_delete_json = json.load(json_file)
        
    for post_to_delete in posts_to_delete_json['posts']:
        response = bot._api.status_delete(post_to_delete.get('mastodon_id'))
        print('deleting post: ', response)
        time.sleep(10)
        
if __name__ == "__main__":
    # Generate json files for posts_to_delete and posts_to_update
    # asyncio.run(generatePostFiles())
    
    # Process the JSON file
    asyncio.run(processJsonFiles())
    
    # Purge old database
    asyncio.run((purgeOldDatabase()))
    
    # Delete old posts from Mastodon
    asyncio.run(deleteOldPosts())