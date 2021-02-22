from rotating_proxies.policy import BanDetectionPolicy

class AmazonBanPolicy(BanDetectionPolicy):
    def response_is_ban(self, request, response):
        # use default rules, but also consider HTTP 200 responses
        # a ban if there is 'captcha' word in response body.
        ban = super(AmazonBanPolicy, self).response_is_ban(request, response)
        print(f'Ban status for ip {request.meta["proxy"]} is {ban} response is {str(response.body)}', flush=True)
        ban = ban or (response.xpath('//title/text()').get() == "Robot Check")
        print(response.xpath('//title/text()').get())
        return ban

    def exception_is_ban(self, request, exception):
        # override method completely: don't take exceptions in account
        return None