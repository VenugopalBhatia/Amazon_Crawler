from setuptools import setup, find_packages

setup(
    name         = 'amazon-product-page-fetcher',
    version      = '0.0.2',
    zip_safe     = True,
    packages     = find_packages(),
    entry_points = {'scrapy': ['settings = amazon_product_page_fetcher.settings']},
)