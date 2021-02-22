# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
from scrapy.exporters import PythonItemExporter
import pika, json
from amazon_product_page_fetcher.mattermost import send_message_to_mattermost

class AmazonProductPageFetcherPipeline:
    def process_item(self, item, spider):
        return item

class RabbitMQPipeline(object):

    def __init__(self, bot_name, rabbitMQ_uri, rabbitMQ_product_page, rabbitMQ_product_page_seeds):
        self.rabbitMQ_uri = rabbitMQ_uri
        self.rabbitMQ_product_page = rabbitMQ_product_page
        self.rabbitMQ_product_page_seeds = rabbitMQ_product_page_seeds
        self.bot_name = bot_name

    def open_spider(self, spider):
        pass
    
    def close_spider(self, spider):
        pass
    
    def _create_mq_connection(self):
        self.connection = pika.BlockingConnection(
            pika.URLParameters(self.rabbitMQ_uri)
            )
        self.channel = self.connection.channel()
        self.exporter = PythonItemExporter(binary=False)

    def process_item(self, item, spider):
        self._create_mq_connection()

        try:
            self.channel.queue_declare(queue=self.rabbitMQ_product_page)
            self.channel.basic_publish(exchange='', routing_key=self.rabbitMQ_product_page, body=json.dumps(self.exporter.export_item(item)))
            self.channel.queue_declare(queue=self.rabbitMQ_product_page_seeds)
            seed = {
                'source_url': item.get('source_url'),
                'seeds': item.get('pages'),
                'pipeline_id': item.get('pipeline_id'),
                'renderer': item.get('renderer'),
                'asin': item.get('asin'),
                'crawl_time': item.get('crawl_time').get("$date")
            }
            self.channel.basic_publish(exchange='', routing_key=self.rabbitMQ_product_page_seeds, body=json.dumps(seed))
            message = (f"""####{ ':red_circle: _Blocked by amazon_' if item.get("blocked") else ""} finished for asin _{item.get("asin")}_\n"""
                "```json\n"+json.dumps(self.exporter.export_item(item), indent=4)+"\n```"
                )
            send_message_to_mattermost(message, self.bot_name)
            spider.logger.info(f'Finished fetching for ASIN: {item.get("asin")}, source URL: {item.get("source_url")}')
        except Exception as exception:
            send_message_to_mattermost(f':red_circle: error occured in {self.bot_name} for asin {item.get("asin")}:{exception}')
            spider.logger.info(
                f'An error occured with pika (RabbitMQ): {exception}')
            spider.crawler.engine.close_spider(
                self, reason='RabbitMQ not responding')
            self.connection.close()
        self.connection.close()
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            bot_name=crawler.settings.get('BOT_NAME'),
            rabbitMQ_uri=crawler.settings.get('RABBITMQ_URI'),
            rabbitMQ_product_page=crawler.settings.get('RABBITMQ_RESULTS'),
            rabbitMQ_product_page_seeds = crawler.settings.get('RABBITMQ_SEEDS')
        )
