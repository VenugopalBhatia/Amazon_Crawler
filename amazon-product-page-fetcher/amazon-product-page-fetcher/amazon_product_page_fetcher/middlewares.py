# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from io import BytesIO
import base64
import threading
import os
import json
import requests
from scrapy.http import HtmlResponse
from scrapy.exceptions import IgnoreRequest
from time import sleep
import sys

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.remote.webelement import WebElement


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

class AmazonProductPageFetcherSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, dict or Item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request, dict
        # or Item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


# class AmazonCaptchaDownloaderMiddleware:
#     # Not all methods need to be defined. If a method is not defined,
#     # scrapy acts as if the downloader middleware does not modify the
#     # passed objects.

#     @classmethod
#     def from_crawler(cls, crawler):
#         # This method is used by Scrapy to create your spiders.
#         s = cls()
#         crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
#         return s

#     def process_request(self, request, spider):
#         # Called for each request that goes through the downloader
#         # middleware.

#         # Must either:
#         # - return None: continue processing this request
#         # - or return a Response object
#         # - or return a Request object
#         # - or raise IgnoreRequest: process_exception() methods of
#         #   installed downloader middleware will be called
#         return None

#     def process_response(self, request, response, spider):
#         # Called with the response returned from the downloader.

#         # Must either;
#         # - return a Response object
#         # - return a Request object
#         # - or raise IgnoreRequest
#         driver = request.meta['driver']
#         wait = WebDriverWait(driver, 10)
#         if self._check_blocked(driver):
#             captcha_image = response.request.meta['screenshot']
#             buffered_image = BytesIO(captcha_image)
#             base64_image = base64.b64encode(buffered_image.getvalue())
#             payload = {}
#             payload['password'] = "theSecretKey007"
#             payload['imageBase64'] = base64_image
#             payload['jobId'] = spider.pipeline_id
#             unraveler_r = requests.post(os.getenv('UNRAVELER_QUESTION'), 
#             data=payload, 
#             headers = {
#                 'content-type': 'application/x-www-form-urlencoded'
#                 })

#             result = json.loads(unraveler_r.text)
#             try:
#                 captcha_answer = self._poll_unraveler_for_answer(result['imageId'])
#                 print(captcha_answer)
#                 captcha_box = self._get_captcha_input(driver, wait)
#                 self._fill_in_captcha(captcha_box, captcha_answer)
#                 response = HtmlResponse(
#                 driver.current_url,
#                 body=str.encode(driver.page_source),
#                 encoding='utf-8',
#                 request=response.request
#                 )
#                 return response
#             except Exception as error:
#                 print(error)
#                 raise IgnoreRequest()
#         else:
#             return response

#     def process_exception(self, request, exception, spider):
#         # Called when a download handler or a process_request()
#         # (from other downloader middleware) raises an exception.

#         # Must either:
#         # - return None: continue processing this exception
#         # - return a Response object: stops process_exception() chain
#         # - return a Request object: stops process_exception() chain
#         pass

#     def spider_opened(self, spider):
#         spider.logger.info('Spider opened: %s' % spider.name)

#     def _check_blocked(self, driver):
#         # page_title = response.xpath('//title/text()').get()
#         page_title = driver.title
#         print("page title is =>>>>>>", page_title)
#         if page_title == "Robot Check":
#             print(
#                 "******************Blocked by Amazon**********************")
#             return True
#         return False

#     @exit_after(180)
#     def _poll_unraveler_for_answer(self, image_id):
#         result = self._check_status(image_id)
#         status = result['status']
#         while status != "ok":
#             sleep(5)
#             result = self._check_status(image_id)
#             status = result['status']
#         return result['answer']

#     def _check_status(self, image_id):
#         unraveler_r = requests.get(f'{os.getenv("UNRAVELER_ANSWER")}/{image_id}')
#         response = json.loads(unraveler_r.text)
#         return response

#     def _fill_in_captcha(self, captcha_box, answer):
#         try:
#             sleep(1)
#             captcha_box.clear()  # Clear the contents
#             sleep(1)
#             captcha_box.send_keys(answer)  # Add the keywords
#             sleep(2)
#             captcha_box.send_keys(Keys.RETURN) 
#         except Exception as exception:
#             print(exception)
#             raise exception
    
#     def _get_captcha_input(self, driver, wait):
#         try:
#             captcha_box = wait.until(ec.visibility_of_element_located(
#                 (By.XPATH, '//*[@id="captchacharacters"]')))
#             # CLick the searchbox by "moving" to that location
#             sleep(2)
#             ActionChains(driver).move_to_element(
#                 captcha_box).click().perform()
#             return captcha_box
#         except Exception as exception:
#             raise exception
