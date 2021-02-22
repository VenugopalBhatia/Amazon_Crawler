# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import pika
from scrapy.exporters import PythonItemExporter
import json

class AmazonProductPageParserPipeline:
    def process_item(self, item, spider):
        return item

class RabbitMQPipeline(object):

    def __init__(self, rabbitMQ_uri, exchange, routing_key):
        self.rabbitMQ_uri = rabbitMQ_uri
        self.exchange = exchange
        self.routing_key = routing_key

    def open_spider(self, spider):
        self.connection = pika.BlockingConnection(
        pika.URLParameters(self.rabbitMQ_uri))
        self.channel = self.connection.channel()
        self.exporter = PythonItemExporter(binary=False)
    
    def close_spider(self, spider):
        self.connection.close()

    def process_item(self, item, spider):
        self.channel.exchange_declare(exchange=self.exchange, exchange_type='topic')
        self.channel.basic_publish(exchange=self.exchange, routing_key=self.routing_key, body=json.dumps(self.exporter.export_item(item)))
    
    @classmethod
    def from_crawler(cls, crawler):
        exchange = getattr(crawler.spider, 'exchange')
        return cls(
            rabbitMQ_uri=crawler.settings.get('RABBITMQ_URI'),
            exchange=exchange,
            routing_key="product-page-parser"
        )