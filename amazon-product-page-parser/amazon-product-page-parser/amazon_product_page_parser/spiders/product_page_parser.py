# -*- coding: utf-8 -*-
import scrapy
from scrapy.loader import ItemLoader
from amazon_product_page_parser.items import Product
import sys
import logging
from datetime import datetime
import os
import esprima 
import json
from time import sleep

class ProductPageParserSpider(scrapy.Spider):
    name = 'product_page_parser_desktop'
    allowed_domains = ['amazon.in']
    exchange = 'jobs'

    @classmethod    
    def from_crawler(cls, crawler, *args, **kwargs):
        # super(ProductPageParserSpider, cls).from_crawler(crawler, *args, **kwargs)
        return cls(
            bot_name=crawler.settings.get('BOT_NAME'),
            *args,
            **kwargs
            )

    def __init__(self, bot_name, seeds=None, task_id=None, pipeline_id=None, source_url=None, crawl_time=None, reprocessed=False, *args, **kwargs):
        super(ProductPageParserSpider, self).__init__(*args, **kwargs)
        if seeds is None or task_id is None:
            sys.exit(0)
        
        if pipeline_id is None:
            sys.exit(0)

        self.task_id = task_id
        self.job_id = kwargs['_job']
        self.pipeline_id = pipeline_id
        self.seeds = seeds.split('|')
        self.source_url = source_url
        self.bot_name = bot_name
        self.crawl_time = crawl_time
        self.reprocessed = bool(reprocessed)
        self.__configure_logger()
        logging.getLogger('pika').setLevel(logging.WARN)

    def __configure_logger(self):
        
        logger = logging.getLogger(self.name)
        
        folder_path = f'/scrapyd/logs-internal/{self.bot_name}/{self.name}/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler(f'{folder_path}/{self.pipeline_id}.log')
        c_handler.setLevel(logging.WARNING)
        f_handler.setLevel(logging.INFO)

        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)
    
    def start_requests(self):
        for seed in self.seeds:
            yield scrapy.Request(seed, callback=self.parse)

    def parse(self, response):
        if self.check_blocked(response):
            return
        product = ItemLoader(item=Product(), response=response)
        asin_info = self.__get_asin_info(response)

        canonical_link = response.xpath('//*[@rel="canonical"]/@href').get()
        asin = os.path.basename(canonical_link) or "Not_Found"
        product.add_value('asin', asin)
        product.add_value('parent_asin', asin_info['parent'])
        product.add_value('children_asin', asin_info['children'])
        product.add_xpath('title', '//span[@id="productTitle"]/text()')
        product.add_xpath('manufacturer', '//a[@id="bylineInfo"]/text()')
        product.add_xpath('rating', '//div[@id="averageCustomerReviews"]//span[@id="acrPopover"]/@title')
        product.add_xpath('rating_count', '//div[@id="averageCustomerReviews"]//span[@id="acrCustomerReviewText"]/text()[normalize-space(.)]')
        product.add_xpath('answered_questions', '//a[@id="askATFLink"]/span/text()[normalize-space(.)]')
        product.add_xpath('promote', '//div[@data-feature-name="acBadge"]//span//text()[normalize-space(.)]')
        product.add_xpath('mrp', '//*[@id="price"]/table/tbody/tr[1]/td[2]/span[1]/text()')
        product.add_xpath('price', '//*[@id="priceblock_ourprice" or @id="priceblock_dealprice"]//text()')
        product.add_xpath('categories', '//*[@id="wayfinding-breadcrumbs_container"]//li[not(contains(@class, "a-breadcrumb-divider"))]/span//text()')
        if response.css('.fbaBadge'):
            product.add_value('fba', True)
        
        offers = []
        print(response.css('.sopp-offer-enumerator').xpath('following-sibling::div'))
        for offer in response.css('.sopp-offer-enumerator').xpath('./following-sibling::div'):
            name = offer.xpath('.//*[@aria-hidden="true"]').css('.sopp-offer-title').xpath('.//text()').get()
            description = offer.xpath('.//*[@aria-hidden="true"]').css('.description').xpath('.//text()').extract()
            if not name == None:
                offers.append(
                    {
                        name: ''.join(description)
                    }
                )
        product.add_value('offers', offers)
        # product.add_xpath('offers', '//*[@class="sopp-offer-title"]/../span/text()[normalize-space(.)]')
        product.add_xpath('extra_features', '//*[@id="icon-farm-container"]/div/div/div[2]//text()[normalize-space(.)]')
        product.add_xpath('expiry_date', '//*[@data-feature-name="expiryDate"]//text()')
        product.add_xpath('availability', '//*[@id="availability"]//text()')
        product.add_xpath('merchant_info', '//*[@id="merchant-info"]//text()')
        product.add_xpath('olp', '//*[@data-feature-name="olp"]//text()')
        styles = []
        index = 0
        for style in response.xpath('//*[@data-feature-name="twister"]//ul/li'):
            name = style.xpath('./@title').get()
            asin = style.xpath('./@data-defaultasin').get()
            price = style.xpath(f'.//*[@id="style_name_{index}_price" or @id="pattern_name_{index}_price"]/span/text()').get()
            style_item = {
                "name": name,
                "asin": asin,
                "price": price
            }

            styles.append(style_item)
            index += 1
        product.add_value('styles', styles)
        product.add_xpath('design', '//*[@id="variation_pattern_name"]/div/span/text()')
        product.add_xpath('features', '//*[@data-feature-name="featurebullets"]//ul/li//text()')
        bsr_selector = response.xpath("//*[@id='SalesRank']//text()[not(parent::style)][normalize-space(.)]")
        
        if bsr_selector:
            bsr = bsr_selector.getall()
        else:
            bsr_selector = response.xpath("//*[contains(@href,'/gp/bestsellers/')]/ancestor-or-self::*[(contains(.,'Rank') or contains(., 'rank')) and (contains(.,'sellers') or contains(.,'Sellers'))][1]")
            bsr = bsr_selector[-1].xpath('.//text()[not(parent::style)][not(parent::noscript)][not(parent::script)]').getall()

        bsr = "NOT_FOUND" if bsr=='' or bsr is None or (len(bsr)>256)else bsr
        dfa_selector = response.xpath("//*[contains(., 'Date First Available')]")
        if dfa_selector and len(dfa_selector) > 0:
            dfa = dfa_selector[-1].xpath('./..//text()[not(parent::style)][not(parent::noscript)][not(parent::script)]').getall()
        else:
            dfa = None
        dfa = "NOT_FOUND" if dfa=='' or dfa is None or (len(dfa)>256)else dfa
        # product.add_xpath('bsr', '//*[@id="SalesRank"]//text()[not(parent::style)][normalize-space(.)]')
        # product.add_xpath('bsr', "//a[contains(@href, '/gp/bestsellers/')]/../../*[contains(.//text(), 'in')][contains(.//text(), '#')]//text()")
        # self.logger.info(bsr[-1].xpath('string(.//text())').getall())
        # product.add_xpath('bsr', "//*[contains(@href,'/gp/bestsellers/')]/ancestor-or-self::*[(contains(.,'Rank') or contains(., 'rank')) and (contains(.,'sellers') or contains(.,'Sellers'))][1]//text()")
        product.add_value('bsr', bsr)
        product.add_value('dfa', dfa)
        product.add_xpath('description', '//*[@id="productDescription"]/p//text()')
        product.add_xpath('aplus_images', '//*[@id="aplus"]//img/@src[not(contains(., "gif"))]')
        product.add_xpath('aplus_text', '//*[@id="aplus"]//*[not(self::style)][not(self::noscript)][not(self::script)]/text()')
        customer_reviews = response.xpath('//*[@id="reviewsMedley"]')

        star_ratings = {}
        print(response.xpath('//*[@id="reviewsMedley"]//table[@id="histogramTable"]'))
        for star_rating in customer_reviews.xpath('.//table[@id="histogramTable"]//tr'):
            star = star_rating.xpath('./td[1]//a/text()[normalize-space(.)]').get()
            percentage = star_rating.xpath('./td[3]//a/text()[normalize-space(.)]').get()
            star_ratings[star] = percentage
        print(star_ratings)
        product.add_value('star_ratings', star_ratings)

        cr_summary = {}
        for summary in customer_reviews.xpath('//*[@id="cr-summarization-attributes-list"]/div'):
            pivot = summary.xpath('.//i')
            attribute = pivot.xpath('./../preceding-sibling::*//span/text()').get()
            rating = pivot.xpath('./span/text()').get()
            cr_summary[attribute] = rating
        product.add_value('cr_summary', cr_summary)
        product.add_value('parse_time', {"$date": datetime.now().isoformat()})
        product.add_value('crawl_time', {"$date": datetime.fromisoformat(self.crawl_time).isoformat()})
        product.add_value('reprocessed', self.reprocessed)
        product.add_value('url', response.request.url)
        product.add_value('source_url', self.source_url)
        product.add_value('pipeline_id', self.pipeline_id)

        yield product.load_item()

    def __get_asin_info(self, response):
        parent_asin = None
        children = None
        try:

            js = response.xpath('//script[@type="text/javascript"][contains(.,"parentAsin")]//text()').get()
            parsed_program = esprima.parseScript(js)
            # prased_program.body
            # print(prased_program)
            # json.dump('parsed_js', prased_program)
            properties = parsed_program.toDict().get('body')[0].get('expression').get('arguments')[-1].get("body").get('body')[0].get('declarations')[0].get("init").get('properties')
            # print(properties)
            for prop in properties:
                if prop.get("type") == "Property" and prop.get('key').get('value') == "parentAsin":
                    parent_asin = prop.get('value').get('value')
                if prop.get("type") == "Property" and prop.get('key').get('value') == "dimensionToAsinMap":
                    children_props = prop.get('value').get('properties')
                    children = map(lambda child: child.get('value').get('value'), children_props)

        except Exception as err:
            self.logger.error(f"An exception occurred {err}")
        asin_info = {
            'parent': parent_asin,
            'children': children
        } 
        print(asin_info)
        return asin_info        
        # with open('parsed_js.js', 'w') as js_file:
        #     js_file.writelines(json.dumps(parsed_program.toDict(), indent=2))

    def check_blocked(self, response):
        page_title = response.xpath('//title/text()').get()
        if page_title == "Robot Check":
            print(
                "******************Blocked by Amazon**********************")
            return True
        return False
