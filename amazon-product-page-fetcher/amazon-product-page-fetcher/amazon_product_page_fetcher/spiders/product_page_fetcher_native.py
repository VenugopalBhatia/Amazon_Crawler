# -*- coding: utf-8 -*-
import scrapy
from time import sleep
from scrapy.http import Request
from .product_page_fetcher import ProductPageFetcherSpider
import random
from scrapy.loader import ItemLoader
from selenium.webdriver.common.proxy import Proxy
import os
import hashlib
from amazon_product_page_fetcher.items import Page
from datetime import datetime
from amazon_product_page_fetcher.mattermost import send_message_to_mattermost

def hash_keyword(url):
    clean_url = remove_ref_from_url(url)
    return hashlib.md5(clean_url.encode('utf-8')).hexdigest()

def remove_ref_from_url(url):
    return url.split('/ref')[0]

class ProductPageFetcherNativeSpider(ProductPageFetcherSpider):
    name = 'product_page_fetcher_desktop_url'
    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 1,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware' : 100,
            'amazon_captcha_detector.AmazonCaptchaDetectorDownloaderMiddleware': 300,
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
        }
    }
    ua_strings = [
        'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6; rv:42.0) Gecko/20100101 Firefox/42.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36 OPR/38.0.2220.41',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
    ]

    @classmethod
    def prepare_settings(cls):
        cls.custom_settings['DOWNLOADER_MIDDLEWARES'] = {
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 1,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware' : 100,
            'amazon-captcha-detector.AmazonCaptchaDetectorDownloaderMiddleware': 200,
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
        }
        cls.custom_settings['HTTPCACHE_ENABLED'] = True
        cls.custom_settings['HTTPCACHE_EXPIRATION_SECS'] = 86400
        cls.custom_settings['HTTPCACHE_DIR'] = 'httpcache'
        cls.custom_settings['HTTPCACHE_STORAGE'] = 'scrapy.extensions.httpcache.FilesystemCacheStorage'
        # cls.custom_settings['AUTOTHROTTLE_ENABLED'] = True
        # cls.custom_settings['AUTOTHROTTLE_TARGET_CONCURRENCY'] = 1.0
        cls.custom_settings['DOWNLOAD_DELAY'] = 2
        cls.custom_settings['CONCURRENT_REQUESTS_PER_DOMAIN'] = 1
        
    @classmethod
    def setup_proxy(cls, proxy_server):
        pass

    def __init__(self, bot_name=None, proxy_service='luminati', seeds=None, seed_type=None, task_id=None, pipeline_id=None, amazon=None, spider_settings=None, *args, **kwargs):
        super().__init__(bot_name=bot_name, proxy_service='luminati', seeds=seeds, seed_type=seed_type, task_id=task_id, pipeline_id=pipeline_id, amazon=amazon, spider_settings=spider_settings, *args, **kwargs)
        self.user_agent = self.browser
        self.headers = {
            'User-Agent': self.browser,
            # 'Accept-Encoding': 'gzip, deflate, br',
            # 'Accept-Language': 'en-US,en;q=0.9',
            # 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        }

    def start_requests(self):
        # yield Request(url="https://www.amazon.in/", callback=self.parse_root)
        

        for index, seed in enumerate(self.seeds):
            sleep(random.randint(3, 15))
            self.logger.info(f'Fetching page for URL at {index} : {seed}')
            if self.seed_type == 'asin':
                self.headers['User-Agent'] = self.__class__.ua_strings[random.randint(0,4)]
                self.blocked_seeds[seed] = 0
                request = Request(url=f'https://{self.amazon}/dp/{seed}', headers=self.headers, dont_filter=True, callback=self.parse, cb_kwargs={'asin': seed})
            elif self.seed_type == 'url':
                self.headers['User-Agent'] = self.__class__.ua_strings[random.randint(0,4)]
                self.blocked_seeds[seed] = 0
                request = Request(url=seed, headers=self.headers, callback=self.parse, cb_kwargs={'asin': seed})

            request.meta['proxy'] = self.proxyServer
            yield request

        # for i in range(20):
        #     # sleep(random.randint(8, 15))
        #     print(i)
        #     seed = f'https://exain.com/proxy/?batch={str(i)}'
        #     self.logger.info(f'Fetching page for URL at {i} : {seed}')
        #     request = Request(url=seed, dont_filter=True, callback=self.parse, cb_kwargs={'asin': seed})
        #     yield request
    
    def parse(self, response, asin):
        blocked = response.request.meta.get('blocked')
        if blocked and self.blocked_seeds[asin] < int(os.getenv('MAX_RETRIES')):
            self.logger.info(f'BLOCKED BY AMAZON!!!')
            sleep(random.randint(15, 40))
            self.blocked_seeds[asin] = self.blocked_seeds[asin] + 1
            self.logger.info(f'BLOCKED BY AMAZON!!!')
            self.logger.info(f'ASIN: {asin} blocked {self.blocked_seeds[asin]} times. Trying once more...')
            send_message_to_mattermost(f'ASIN: {asin} blocked {self.blocked_seeds[asin]} times. Trying once more...', self.bot_name)
            self.headers['User-Agent'] = self.__class__.ua_strings[random.randint(0,4)]
            request = Request(url=f'https://{self.amazon}/dp/{asin}', headers=self.headers, dont_filter=True, callback=self.parse, cb_kwargs={'asin': asin})
            if self.blocked_seeds[asin] < 4:
                request.meta['proxy'] = os.getenv('PROXY')
            else:
                request.meta['proxy'] = os.getenv('PROXY1')
            yield request
        else:
            try:
                loader = ItemLoader(item=Page(), response=response)
            except Exception as exception:
                print(exception)

            url_hash = hash_keyword(response.request.url)
            
            self.save_file(response.body.decode('utf-8'), url_hash)
            canonical_link = "NOT_FOUND"
            canonical_link = response.xpath('//*[@rel="canonical"]/@href').get()
            print(response.xpath('//*[@rel="canonical"]/@href'), canonical_link)
            try:
                canonical_asin = os.path.basename(canonical_link) or "NOT_FOUND"
            except Exception as error:
                self.missed_asins.append(response.request.url)
                self.logger.error(error)
                canonical_asin = "NOT_FOUND"
            loader.add_value('asin', asin)
            loader.add_value('canonical_asin', canonical_asin)
            loader.add_value('canonical_link', canonical_link)
            loader.add_value('source_url', response.request.url)
            loader.add_value('pages', self.urls[url_hash])
            loader.add_value('crawl_time', {"$date": datetime.now().isoformat()})
            loader.add_value('task_id', self.task_id)
            loader._add_value('job_id', self.job_id)
            loader.add_value('pipeline_id', self.pipeline_id)
            loader.add_value('browser', self.browser)
            loader.add_value('renderer', 'desktop')
            loader.add_value('blocked', blocked)
            yield loader.load_item()

    def parse_root(self, response):
        print(response.xpath('//title/text()').get())

    def check_blocked(self, response):
        page_title = response.xpath('//title/text()').get()

        if page_title == 'Robot Check':
            return True
        return False