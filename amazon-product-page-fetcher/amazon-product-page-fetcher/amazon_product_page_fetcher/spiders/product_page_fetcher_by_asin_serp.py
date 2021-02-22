import scrapy
import random
import hashlib
import sys
from scrapy.exceptions import CloseSpider
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep
from .product_page_fetcher import ProductPageFetcherSpider
import json
from scrapy.http import HtmlResponse
from io import BytesIO
import base64
import requests
import os
from datetime import datetime
from amazon_product_page_fetcher.items import Page 
from scrapy.loader import ItemLoader
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from scrapy_selenium import SeleniumRequest
import logging

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

def hash_asin(asin):
    return hashlib.md5(asin.encode('utf-8')).hexdigest()

class ProductPageFetcherByAsinSerpSpider(ProductPageFetcherSpider):
    name = 'product_page_fetcher_by_asin_serp_desktop'

    # def __init__(self, bot_name=None, seeds=None, seed_type=None, task_id=None, pipeline_id=None, amazon=None, spider_settings=None, *args, **kwargs):
    #     super().__init__(bot_name=bot_name, seeds=seeds, seed_type=seed_type, task_id=task_id, pipeline_id=pipeline_id, amazon=amazon, spider_settings=spider_settings, *args, **kwargs)
        # if seeds is None or task_id is None:
        #     sys.exit(0)

        # if pipeline_id is None:
        #     sys.exit(0)

        # if amazon is None or amazon not in self.allowed_domains_dict:
        #     logging.info("No specific region is defined. Therefore crawling default www.amazon.com")
        #     self.amazon = self.allowed_domains_dict.get('IN')
        # else:
        #     logging.info("Starting specific crawling of "+self.allowed_domains_dict.get(amazon))
        #     self.amazon = self.allowed_domains_dict.get(amazon)

        # setts = json.loads(spider_settings)

        # for k in setts:
        #     setting = k + "=" + setts[k]
        #     self.custom_settings['SELENIUM_DRIVER_ARGUMENTS'].append(setting)

        # proxy_r = requests.post(os.getenv('PROXY_API_URL'), 
        #     data={
        #         'pass': os.getenv('PROXY_API_PASSWORD'), 
        #         'user': os.getenv('PROXY_API_USER'), 
        #         'source': self.name, 
        #         'type': os.getenv('PROXY_API_TYPE')
        #         })

        # proxy_details = json.loads(proxy_r.text)
        # if proxy_details['status'] == 'ok':
        #     self.proxyServer = proxy_details['server']
            
        # self.task_id = task_id
        # self.job_id = kwargs['_job']
        # self.pipeline_id = pipeline_id
        # self.seeds = seeds.split('|')
        # self.browser = setts['user-agent']
        # self.bot_name = bot_name
        # self.seed_type = seed_type
        # # self.__configure_logger()

        # if seed_type is None:
        #     self.logger.info(f'Seed Type can not be : {seed_type}')
        #     raise CloseSpider()

        # self.logger.info(f'\n \nJob Id: {self.job_id} \nPipeline Id: {self.pipeline_id} \nTask Id: {self.task_id}\n')
        # self.logger.info(f'Number of ASINs assigned: {len(self.seeds)}')
        # self.logger.info(f'Proxy server for the spider is: {self.proxyServer}')
        # self.logger.info(f'User Agent for the spider is: {self.browser}')
        # logging.getLogger('pika').setLevel(logging.WARN)


    def start_requests(self):
        # Just instantiate a URL from within Scrapy
        yield SeleniumRequest(url="https://"+self.amazon, dont_filter=True, callback=self.parse)

    def parse(self, response):
        for (index, seed) in enumerate(self.seeds):
            # sleep(random.uniform(8, 13))
            asin = os.path.basename(seed)
            self.logger.info(f'Starting search for ASIN number {index + 1} : "{asin}"')
            yield self.search_asin(response, asin)

    def search_asin(self, response, asin):
        driver = response.request.meta['driver']
        wait = WebDriverWait(driver, 10)

        asin_hash = hash_asin(asin)

        searchbox = self.go_to_searchbox(driver, wait)
        sleep(random.uniform(0.5,3))
        searchbox.clear()  # Clear the contents
        # sleep(random.uniform(0,1))
        for char in asin:
            sleep(random.uniform(0,0.01))
            searchbox.send_keys(char)  # Add the keywords

        sleep(random.uniform(0,1))
        searchbox.send_keys(Keys.RETURN)
        sleep(random.uniform(2,5))

        result = self.ensure_result(driver)

        if not result:
            self.logger.info(f'If captcha occurred, then correct captcha resolutino failed "for search" and therefore early exit from parse for asin {asin}')
            return
        
        try:
            wait.until(ec.visibility_of_element_located((By.XPATH, f'//*[@data-asin="{asin}"]')))
        except TimeoutException as texception:
            self.missed_asins.append(asin)
            self.logger.exception(texception)
            self.logger.info(f'''\nTimed out while waiting for attribute located at XPATH=//*[@data-asin="{asin}"]. \n
            Possibly because searching amazon for {asin} returned no desired result.
            ''')
            return

        product_element = driver.find_element_by_xpath(f'//*[@data-asin="{asin}"]')
        product_image = driver.find_element_by_xpath(f'//*[@data-asin="{asin}"]//h2/a')

        sleep(random.uniform(0, 4))
        actions = ActionChains(driver)
        actions.move_to_element(product_element)
        sleep(random.uniform(0, 1))
        actions.click(product_image)
        try:
            actions.perform()
        except Exception as exception:
            self.logger.exception(exception)
            return
            
        sleep(random.uniform(0, 1))

        tabs = driver.window_handles

        driver.close()
        # tabs = driver.window_handles

        self.logger.info(f'Switching tab')
        driver.switch_to.window(tabs[1])

        result = self.ensure_result(driver)
        if not result:
            self.logger.info(f'If captcha occurred, then correct captcha resolutino failed for "new tab" and therefore early exit from parse for asin {asin}')
            return

        wait.until(ec.visibility_of_element_located((By.XPATH, f'//*[@id="productTitle"]')))

        self.save_file(driver.page_source, asin_hash)

        try:
            loader = ItemLoader(item=Page(), response=response)
        except Exception as exception:
            print(exception)

        # canonical_link = result.xpath('//*[@rel="canonical"]/@href').get()
        # asin = os.path.basename(canonical_link) or "Not_Found"
        
        loader.add_value('asin', asin)
        loader.add_value('source_url', result.url)
        loader.add_value('pages', self.urls[asin_hash])
        loader.add_value('crawl_time', {"$date": datetime.now().isoformat()})
        loader.add_value('task_id', self.task_id)
        loader._add_value('job_id', self.job_id)
        loader.add_value('pipeline_id', self.pipeline_id)
        loader.add_value('browser', self.browser)
        loader.add_value('renderer', self.name.replace('product_page_fetcher_by_asin_serp_', ''))

        return loader.load_item()

    def ensure_result(self, driver):
        wait = WebDriverWait(driver, 10)

        blocked = self.check_blocked(driver)
        captcha_fill_attempts = 0

        while blocked and captcha_fill_attempts < 3:
            captcha_image = driver.get_screenshot_as_png()
            buffered_image = BytesIO(captcha_image)
            base64_image = base64.b64encode(buffered_image.getvalue())
            payload = {}
            payload['password'] = os.getenv('UNRAVELER_PASSWORD')
            payload['imageBase64'] = base64_image
            payload['jobId'] = self.pipeline_id

            self.logger.info(f'Sending captcha to Unraveler with jobId {payload["jobId"]}')

            unraveler_r = requests.post(os.getenv('UNRAVELER_QUESTION'), 
            data=payload, 
            headers = {
                'content-type': 'application/x-www-form-urlencoded'
                })

            result = json.loads(unraveler_r.text)

            self.logger.info(f'Received response from Unraveler {result}')

            try:
                captcha_answer = self.poll_unraveler_for_answer(result['imageId'])
                captcha_box = self.get_captcha_input(driver, wait)
                self.fill_in_captcha(captcha_box, captcha_answer)
                captcha_fill_attempts = captcha_fill_attempts + 1
                blocked = self.check_blocked(driver)
                if blocked:
                    continue
                response = HtmlResponse(
                    driver.current_url,
                    body=str.encode(driver.page_source),
                    encoding='utf-8'
                )
                # return True
                return response
            except Exception as error:
                self.logger.exception(error)
                # return False
                return None
        else:
            if captcha_fill_attempts == 3:
                self.logger.info(f'Exhausted maximum number of captcha attempts: {captcha_fill_attempts}')
                # return False
                return None
            response = HtmlResponse(
                    driver.current_url,
                    body=str.encode(driver.page_source),
                    encoding='utf-8'
                )
            return response

    def go_to_searchbox(self, driver, wait):
        try:
            searchbox = wait.until(ec.visibility_of_element_located(
                (By.XPATH, '//*[@id="twotabsearchtextbox"]')))
            # CLick the searchbox by "moving" to that location
            sleep(random.uniform(0, 1))
            ActionChains(driver).move_to_element(
                searchbox).click().perform()
            return searchbox
        except:
            self.logger.error(
                "Search Input Box not Found on page. No reason to continue.")
            raise CloseSpider('Search Box not found')

    def check_blocked(self, driver):
        # page_title = response.xpath('//title/text()').get()
        page_title = driver.title
        print("page title is =>>>>>>", page_title)
        if page_title == "Robot Check":
            self.logger.warn("Blocked by amazon")
            return True
        return False

    @exit_after(180)
    def poll_unraveler_for_answer(self, image_id):
        result = self.check_status(image_id)
        status = result['status']
        while status != "ok":
            sleep(5)
            result = self.check_status(image_id)
            status = result['status']
        return result['answer']

    def check_status(self, image_id):
        unraveler_r = requests.get(f'{os.getenv("UNRAVELER_ANSWER")}/{image_id}')
        response = json.loads(unraveler_r.text)
        return response

    def fill_in_captcha(self, captcha_box, answer):
        try:
            sleep(1)
            captcha_box.clear()  # Clear the contents
            sleep(1)
            captcha_box.send_keys(answer)  # Add the keywords
            sleep(2)
            captcha_box.send_keys(Keys.RETURN) 
        except Exception as exception:
            print(exception)
            raise exception
    
    def get_captcha_input(self, driver, wait):
        try:
            captcha_box = wait.until(ec.visibility_of_element_located(
                (By.XPATH, '//*[@id="captchacharacters"]')))
            # CLick the searchbox by "moving" to that location
            sleep(2)
            ActionChains(driver).move_to_element(
                captcha_box).click().perform()
            return captcha_box
        except Exception as exception:
            self.logger.error(
                "Captcha Input Box not Found on page. No reason to continue.")
            raise exception