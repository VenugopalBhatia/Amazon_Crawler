# -*- coding: utf-8 -*-
from __future__ import print_function
import scrapy
from scrapy.exceptions import CloseSpider
import sys
import logging
import urllib
import hashlib
import os
import json
import requests
from scrapy.loader import ItemLoader
from amazon_product_page_fetcher.items import Page
from datetime import datetime
from scrapy_selenium import SeleniumRequest
import math
from io import BytesIO
import base64
import configparser
from dotenv import load_dotenv
from pathlib import Path  # python3 only
import random
# Selenium Specific & Related Imports
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.proxy import Proxy
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.remote_connection import LOGGER
from scrapy.http import HtmlResponse
from urllib import parse
import sentry_sdk
from PIL import Image
from amazon_product_page_fetcher.mattermost import send_message_to_mattermost
import threading
try:
    import thread
except ImportError:
    import _thread as thread
    
try: # use code that works the same in Python 2 and 3
    range, _print = xrange, print
    def print(*args, **kwargs): 
        flush = kwargs.pop('flush', False)
        _print(*args, **kwargs)
        if flush:
            kwargs.get('file', sys.stdout).flush()            
except NameError:
    pass

# config = configparser.ConfigParser()
# config.read('scrapy.cfg')
# project = config['deploy']['project']
# env_path = Path(f'/envs/{project}') / '.env'
# load_dotenv(dotenv_path=env_path)
# print(env_path)
def cdquit(fn_name):
    # print to stderr, unbuffered in Python 2.
    print('{0} took too long'.format(fn_name), file=sys.stderr)
    sys.stderr.flush() # Python 3 stderr is likely buffered.
    thread.interrupt_main() # raises KeyboardInterrupt
    
def exit_after(s):
    '''
    use as decorator to exit process if 
    function takes longer than s seconds
    '''
    def outer(fn):
        def inner(*args, **kwargs):
            timer = threading.Timer(s, cdquit, args=[fn.__name__])
            timer.start()
            try:
                result = fn(*args, **kwargs)
            finally:
                timer.cancel()
            return result
        return inner
    return outer
LOGGER.setLevel(logging.WARNING)

def hash_keyword(url):
    clean_url = remove_ref_from_url(url)
    return hashlib.md5(clean_url.encode('utf-8')).hexdigest()

def remove_ref_from_url(url):
    return url.split('/ref')[0]

class ProductPageFetcherSpider(scrapy.Spider):
    old_factory = logging.getLogRecordFactory()
    name = 'product_page_fetcher_desktop'
    allowed_domains_dict = {
        'IN': 'www.amazon.in',
        'US': 'www.amazon.us',
        'GLOBAL': 'www.amazon.com'
    }
    allowed_domains = allowed_domains_dict.values()
    custom_settings = {
        #Selenium configurations
        'SELENIUM_DRIVER_NAME' : os.getenv('SELENIUM_DRIVER_NAME'),
        # 'SELENIUM_DRIVER_NAME' : webdriver.Firefox(),
        'SELENIUM_DRIVER_ARGUMENTS' : os.getenv('SELENIUM_DRIVER_ARGUMENTS').split('|'),  # '--headless' if using chrome instead of firefox
        'SELENIUM_COMMAND_EXECUTOR' : os.getenv('SELENIUM_COMMAND_EXECUTOR'),
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        sentry_webhook = os.getenv('SENTRY_WEBHOOK')
        sentry_sdk.init(sentry_webhook)
        return cls(
            bot_name=crawler.settings.get('BOT_NAME'),
            *args,
            **kwargs
            )
    
    @classmethod
    def setup_proxy(cls, proxy_server):
        proxy = Proxy({'proxyType': 'MANUAL', 'httpProxy': proxy_server, 'sslProxy': proxy_server})

        cls.custom_settings['SELENIUM_PROXY'] = proxy

    @classmethod
    def prepare_settings(cls):
        pass
        cls.custom_settings['DOWNLOADER_MIDDLEWARES'] = {
            'scrapy_selenium.SeleniumMiddleware': 800,
            'amazon_captcha_solver.AmazonCaptchaDownloaderMiddleware': 900
        }

    def __init__(self, bot_name=None, proxy_service='1ds', seeds=None, seed_type=None, task_id=None, pipeline_id=None, amazon=None, spider_settings=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if seeds is None or task_id is None:
            sys.exit(0)

        if pipeline_id is None:
            sys.exit(0)

        if amazon is None or amazon not in ProductPageFetcherSpider.allowed_domains_dict:
            logging.info("No specific region is defined. Therefore crawling default www.amazon.com")
            self.amazon = ProductPageFetcherSpider.allowed_domains_dict.get('IN')
        else:
            logging.info("Starting specific crawling of "+ProductPageFetcherSpider.allowed_domains_dict.get(amazon))
            self.amazon = ProductPageFetcherSpider.allowed_domains_dict.get(amazon)

        if spider_settings:

            setts_json = json.loads(spider_settings)
            self.urls = {}

            for k in setts_json:
                setting = k + "=" + setts_json[k]
                ProductPageFetcherSpider.custom_settings['SELENIUM_DRIVER_ARGUMENTS'].append(setting)
        
        self.__class__.prepare_settings()
        self.proxy_service = proxy_service
        self.blocked_urls = []
        self.blocked_seeds = {}
        if proxy_service == '1ds':
            # 1DS proxy setup
            proxy_r = requests.post(os.getenv('PROXY_API_URL'), 
                data={
                    'pass': os.getenv('PROXY_API_PASSWORD'), 
                    'user': os.getenv('PROXY_API_USER'), 
                    'source': self.name, 
                    'type': os.getenv('PROXY_API_TYPE')
                    })

            proxy_details = json.loads(proxy_r.text)
            if proxy_details['status'] == 'ok':
                self.proxyServer = proxy_details['server']
                self.__class__.setup_proxy(self.proxyServer)

        elif proxy_service == 'luminati':
            # Luminati proxy setup
            # l_username = os.getenv('LUMINATI_USERNAME')
            # l_password = os.getenv('LUMINATI_PASSWORD')
            # l_port = os.getenv('LUMINATI_PORT')
            # l_session = random.random()
            # self.proxyServer = f'zproxy.lum-superproxy.io:{l_port}'
            # proxy = Proxy({'proxyType': 'MANUAL', 'httpProxy': self.proxyServer, 'sslProxy': self.proxyServer})
            # proxy.socksUsername = f'{l_username}-country-in-session-{l_session}'
            # proxy.socksPassword = l_password
            # self.custom_settings['SELENIUM_PROXY'] = proxy
            self.proxyServer = os.getenv('PROXY')
            self.__class__.setup_proxy(self.proxyServer)
        else:
            self.logger.info('No proxy service defined. Using default proxy')
            
        self.task_id = task_id
        self.job_id = kwargs['_job']
        self.pipeline_id = pipeline_id
        self.seeds = seeds.split('|')
        self.browser = setts_json['user-agent']
        self.bot_name = bot_name
        self.seed_type = seed_type
        self.missed_asins = []
        self.__configure_logger()

        if seed_type is None:
            self.logger.info(f'Seed Type can not be : {seed_type}')
            raise CloseSpider()
        
        self.logger.info(f'\n\nJob Id: {self.job_id}\nPipeline Id: {self.pipeline_id}\nTask Id: {self.task_id}\n')
        self.logger.info(f'Begin Time: {datetime.now()}')
        self.logger.info(f'Number of ASINs assigned: {len(self.seeds)}')
        self.logger.info(f'Proxy server for the spider is: {self.proxyServer}')
        self.logger.info(f'User Agent for the spider is: {self.browser}')
        job_info = {
            "asins": self.seeds,
            "# of asins": len(self.seeds),
            "proxy": self.proxyServer,
            "pipeline_id": self.pipeline_id,
            "job_id": self.job_id,
            "seed_type": self.seed_type
        }
        message = (f"#### New Job \n"+"```json\n"+json.dumps(job_info, indent=4)+"\n```")
        send_message_to_mattermost(message, self.bot_name)
        logging.getLogger('pika').setLevel(logging.WARN)
    
    def __configure_logger(self):
        
        logger = logging.getLogger(self.name)
        extra = {
            'job_id': self.job_id,
            'pipeline_id': self.pipeline_id
        }
        folder_path = f'/scrapyd/logs-internal/{self.bot_name}/{self.name}/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler(f'{folder_path}/{self.pipeline_id}.log')
        c_handler.setLevel(logging.WARNING)
        f_handler.setLevel(logging.INFO)
        
        logging.setLogRecordFactory(self.record_factory)
        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(name)s - %(pipeline_id)s - %(job_id)s - %(levelname)s - %(message)s')
        f_format = logging.Formatter('%(asctime)s - %(pipeline_id)s - %(job_id)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

    def record_factory(self, *args, **kwargs):
        
        record = self.__class__.old_factory(*args, **kwargs)
        record.job_id = self.job_id
        record.pipeline_id = self.pipeline_id        
        return record

    def start_requests(self):
        
        # yield SeleniumRequest(url="https://www.amazon.in/", callback=self.parse_root)
        for index, seed in enumerate(self.seeds):
            sleep(random.randint(3, 15))
            self.logger.info(f'Fetching page for URL/ASIN at {index} : {seed}')
            if self.seed_type == 'asin':
                yield scrapy.Request(url=f'https://{self.amazon}/dp/{seed}', callback=self.parse, cb_kwargs={'asin': seed})
            elif self.seed_type == 'url':
                # yield SeleniumRequest(url=seed, callback=self.parse, screenshot=True)
                yield scrapy.Request(url=seed, callback=self.parse)
    
    def parse_root(self, response):
        print(response.xpath('//title/text()').get())

    def parse(self, response, asin=None):
        # driver = response.request.meta['driver']
        # wait = WebDriverWait(driver, 10)
        # if self.check_blocked(driver):
        #     captcha_image = response.request.meta['screenshot']
        #     buffered_image = BytesIO(captcha_image)
        #     base64_image = base64.b64encode(buffered_image.getvalue())
        #     payload = {}
        #     payload['password'] = "theSecretKey007"
        #     payload['imageBase64'] = base64_image
        #     payload['jobId'] = self.pipeline_id
        #     unraveler_r = requests.post(os.getenv('UNRAVELER_QUESTION'), 
        #     data=payload, 
        #     headers = {
        #         'content-type': 'application/x-www-form-urlencoded'
        #         })

        #     result = json.loads(unraveler_r.text)
        #     try:
        #         captcha_answer = self.poll_unraveler_for_answer(result['imageId'])
        #         print(captcha_answer)
        #         captcha_box = self.get_captcha_input(driver, wait)
        #         self.fill_in_captcha(captcha_box, captcha_answer)
        #         response = HtmlResponse(
        #         driver.current_url,
        #         body=str.encode(driver.page_source),
        #         encoding='utf-8',
        #         request=response.request
        #         )
        #     except Exception as error:
        #         print(error)
        #         return

        try:
            loader = ItemLoader(item=Page(), response=response)
        except Exception as exception:
            print(exception)

        url_hash = hash_keyword(response.request.url)

        # try:
        #     aplus_element = wait.until(ec.visibility_of_element_located((By.ID, 'aplus')))
        #     ActionChains(driver).move_to_element(aplus_element)
        #     full_page_ss = response.request.meta['screenshot']
        #     ss = self.get_ss_of_element(aplus_element, full_page_ss)
        # except Exception as error:
        #     print(error)
        #     self.logger.error("No A Plus Page")
        
        self.save_file(response.body.decode('utf-8'), url_hash)
        
        canonical_link = "NOT_FOUND"
        canonical_link = response.xpath('//*[@rel="canonical"]/@href').get()
        try:
            canonical_asin = os.path.basename(canonical_link) or "Not_Found"
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
        loader.add_value('renderer', ProductPageFetcherSpider.name.replace('product_page_fetcher_', ''))
        return loader.load_item()

    def closed(self, reason):
        self.logger.info(f'Number of ASINs/URLs missed : {len(self.missed_asins)}')
        if len(self.missed_asins) > 0:
            self.logger.info(f'Missed ASINs/URLs are: {self.missed_asins}')
        self.logger.info(f'Spider closed : {reason}')
    # @exit_after(180)
    # def poll_unraveler_for_answer(self, image_id):
    #     result = self.check_status(image_id)
    #     status = result['status']
    #     while status != "ok":
    #         sleep(5)
    #         result = self.check_status(image_id)
    #         status = result['status']
    #     return result['answer']

    # def check_status(self, image_id):
    #     unraveler_r = requests.get(f'{os.getenv("UNRAVELER_ANSWER")}/{image_id}')
    #     response = json.loads(unraveler_r.text)
    #     return response

    # def fill_in_captcha(self, captcha_box, answer):
    #     try:
    #         sleep(1)
    #         captcha_box.clear()  # Clear the contents
    #         sleep(1)
    #         captcha_box.send_keys(answer)  # Add the keywords
    #         sleep(2)
    #         captcha_box.send_keys(Keys.RETURN) 
    #     except Exception as exception:
    #         print(exception)
    #         raise exception
    
    # def get_captcha_input(self, driver, wait):
    #     try:
    #         captcha_box = wait.until(ec.visibility_of_element_located(
    #             (By.XPATH, '//*[@id="captchacharacters"]')))
    #         # CLick the searchbox by "moving" to that location
    #         sleep(2)
    #         ActionChains(driver).move_to_element(
    #             captcha_box).click().perform()
    #         return captcha_box
    #     except Exception as exception:
    #         self.logger.error(
    #             "Captcha Input Box not Found on page. No reason to continue.")
    #         raise exception

    def get_ss_of_element(self, element: WebDriverWait, full_page_ss):
        x = element.location["x"]
        y = element.location["y"]
        w = element.size["width"]
        h = element.size["height"]
        im = Image.open(BytesIO(full_page_ss))
        left=math.floor(x)
        top=math.floor(y)
        right= x + math.ceil(w)
        bottom= y + math.ceil(h)
        # return im.crop((18, 2165, 1333, 3134))
        return im.crop((left, top, right, bottom))
        # return im


    def save_file(self, data, url_hash):
        # url_hash = hash_url(response.url)
        # data = data  # .body.decode("utf-8")
        file_path = self.file_location(url_hash)
        try:
            with open(file_path, "w") as file:
                self.logger.info(f'Saving file at {file_path}')
                file.write(data)
        except IOError:
            self.logger.error(f'Unable to write file at {file_path}')

        self.urls[url_hash].append(self.http_url_for_file_path(file_path))
        # if url_hash in self.urls:
        #     self.urls[url_hash].append(file_path)
        # else:
        #     self.urls[url_hash] = [file_path]

    def http_url_for_file_path(self, file_path: str):
        return f"https://{os.getenv('STORAGE_HOSTNAME')}.storage.1digitalstack.com/"+file_path.split('/storage/')[1]

    def file_location(self, url_hash):
        
        time = datetime.now()
        folder = time.strftime("%Y%m%d")
        folder_path = "/storage/"+folder+"/"+self.pipeline_id+"/"+self.job_id
        if not os.path.exists(folder_path):
            print("creating folder")
            os.makedirs(folder_path)

        if not url_hash in self.urls:
            self.urls[url_hash] = []
        file_path = folder_path+"/"+url_hash + \
            "_" + str(len(self.urls[url_hash]))
        return file_path

    # def next_page_url(self, response):
    #     # print(response.body.decode("utf-8"))
    #     query = urllib.parse.urlparse(response.xpath(
    #         '//*[normalize-space(text()) = "Next"]//@href').get()).query
    #     # print(urllib.parse.urlparse(response.xpath('//*[normalize-space(text()) = "Next"]//@href').get()))
    #     if query:
    #         return self.base_url + query
    #     else:
    #         return None

    def check_blocked(self, driver):
        # page_title = response.xpath('//title/text()').get()
        page_title = driver.title
        if page_title == "Robot Check":
            print(
                "******************Blocked by Amazon**********************")
            return True
        return False
