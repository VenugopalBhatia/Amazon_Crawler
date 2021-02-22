import os
import requests

def send_message_to_mattermost(message, bot_name):
        try:
            mw = os.getenv('MATTERMOST_WEBHOOK')
            payload = {
                "channel": "amazon-product-page-crawler",
                "username": f'{bot_name}',
                "icon_url": "https://www.mattermost.org/wp-content/uploads/2016/04/icon.png",
                "text": message
            }
            mattermost_r = requests.post(mw,json=payload)
        except Exception as exception:
            print(exception)