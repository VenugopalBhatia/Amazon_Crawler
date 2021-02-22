# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.loader.processors import Compose, TakeFirst, Join, MapCompose

class AmazonProductPageFetcherItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class Page(scrapy.Item):
    source_url = scrapy.Field(output_processor=TakeFirst())
    asin = scrapy.Field(output_processor=TakeFirst())
    canonical_asin = scrapy.Field(output_processor=TakeFirst())
    canonical_link = scrapy.Field(output_processor=TakeFirst())
    pages = scrapy.Field()
    crawl_time = scrapy.Field(output_processor=TakeFirst())
    pipeline_id = scrapy.Field(output_processor=TakeFirst()) 
    job_id = scrapy.Field(output_processor=TakeFirst())
    task_id = scrapy.Field(output_processor=TakeFirst())
    renderer = scrapy.Field(output_processor=TakeFirst())
    browser = scrapy.Field(output_processor=TakeFirst())
    blocked = scrapy.Field(output_processor=TakeFirst())
    product_detail_ss = scrapy.Field()