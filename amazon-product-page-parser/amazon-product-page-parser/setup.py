from setuptools import setup, find_packages

setup(
    name         = 'amazon-product-page-parser',
    version      = '0.0.1',
    zip_safe     = True,
    packages     = find_packages(),
    entry_points = {'scrapy': ['settings = amazon_product_page_parser.settings']},
)