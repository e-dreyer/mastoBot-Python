# MastoBot-Python

MastoBot is a generic Python package which allows for customizable Mastodon bots to be created. This bots can do anything from simply liking posts by specific users, cross-posting to other platforms or simulating Mastodon groups. One such example is the implementation for the [3D printing group bot](https://github.com/e-dreyer/mastoBot-3D).

## Motivation

Mastodon allows for the use of hashtags on the platform. Users can use these hashtags to allow others to subscribe to topics and search for trends. These hashtags however suffer from the lack of moderation. Malicious users are able to hijack trends and topics by simply using the tags in their posts. Users are unable to avoid such post except for muting or blocking such users.

As Mastodon has grown in popularity the need for larger communities and discussions has grown. This bot allows users to mention the username of the bot, no different from mentioning any other user. The bot can then perform certain actions on this post. This most common reaction is to boost the post for other users following the bot to see. Moderators can then remove rule-breaking posts, block user on their current account and new accounts they move to and run various other automation. Such groups can also be made open-source to allow the community to contribute to the development of the bot. Such groups grant moderators more granular control and allows for an improved experience for communities.

As the project grew, the implementation became more generic and the original idea was forked and this package was created.

## Configuration

### Config.py

`config.py` is used to load custom configs and modified implementations. It allows for the specification of parameters that change the behavior of the bot. Currently no main-stream functionality is included using this file, but it has already been added for future features.

### Credentials.py

`credentials.py` is used to load custom credentials and is kept separate to allow for the sharing of configs and implementations, but keeping credentials secret.

Currently the following credentials are implemented and should be provided in `credentials.yml`:

- mastodon:
    secret: Your Mastodon `secret` key, found under `development` in your settings
    base_url: Your base `url` for my instance it would be `"https://techhub.social/"`

### Docker

For simplicity the main focus of this bot has been to develop it to run in `Docker`. This allows for a simpler deployment of the bot and binds all of its components together. It also allows less technical users to easily host multiple bots and track their performance.

## Installation

To start, first install this package in your project

    ```bash
    pip install git+https://github.com/e-dreyer/mastoBot
    ```

The pip installation can then be frozen to create a requirements file

    ```bash
    pip freeze > requirements.txt
    ```

From here the package can simply be imported and used.

## Usage

Start by first copying the `credentials.yml` and `config.yml` files from the example folder. Add your desired config to `config.yml` and copy and paste the required credentials into you `credentials.yml` file. These credentials can be found on your Mastodon profile, under settings > development.

Import the following modules and packages:

    ```python
    from mastoBot.configManager import ConfigAccessor
    from mastoBot.mastoBot import MastoBot, handleMastodonExceptions
    ```

Then create a new class inheriting from `MastoBot`. The following code can be copied directly. Each of these functions are required to be implemented and will automatically be executed for all notifications received over the Mastodon API. Thus, you can specify the behavior for each type of notification.

    ```python
    class MyBot(MastoBot):
        @handleMastodonExceptions
        def processMention(self, mention: Dict):
            self.dismissNotification(mention.get("id"))

        @handleMastodonExceptions
        def processReblog(self, reblog: Dict):
            self.dismissNotification(reblog.get("id"))

        @handleMastodonExceptions
        def processFavourite(self, favourite: Dict):
            self.dismissNotification(favourite.get("id"))

        @handleMastodonExceptions
        def processFollow(self, follow: Dict):
            self.dismissNotification(poll.get("id"))

        @handleMastodonExceptions
        def processPoll(self, poll: Dict):
            self.dismissNotification(poll.get("id"))

        @handleMastodonExceptions
        def processFollowRequest(self, follow_request: Dict):
            self.dismissNotification(follow_request.get("id"))
    ```

Then all that is left to do is run the `main` function

    ```python
    class MyBot(MastoBot):
        ...

    if __name__ == "__main__":
        # Your config is imported here. ConfigAccessor allows us to easily extend these files and get errors for incorrect and missing fields and values
        config = ConfigAccessor("config.yml")
        credentials = ConfigAccessor("credentials.yml")

        # Create an instance of your bot
        bot = MyBot(credentials=credentials, config=config)

        # Run the bot
        bot.run()
    ```

As an example, here is an implementation for sending a welcoming message to all new followers:

    ```python
    def processFollow(self, follow: Dict):
            # The follow notification is automatically passed as a parameter to this function
            # We use this notification to get the account of the new follower
            api_account = self.getAccount(follow.get("account"))

            # We then get the username@domain value of the account
            account = api_account.get("acct")

            # We can then try to import a Jinja2 template
            try:
                file_loader = FileSystemLoader("templates")
                env = Environment(loader=file_loader)
                template = env.get_template("new_follow.txt")
                output = template.render(account=account)
            except Exception as e:
                logging.critical("Error initializing template")
                raise e

            # The template can then be rendered
            try:
                self._api.status_post(status=output, visibility="direct")
            except Exception as e:
                logging.critical("Error posting Status")
                raise e

            logging.info(f"Follow processed: {follow.get('id')}")

            # Finally, we can dismiss the notification at the API level.
            # This basically deletes the notification and this function will not be called for it again
            self.dismissNotification(follow.get("id"))
    ```

Finally, you can simply run:

    ```bash
    docker-compose up -d --build
    ```

And your bot will be up and running in Docker!
