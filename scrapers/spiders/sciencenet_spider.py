import scrapy
import re
import urllib
import json


def authentication_failed(response):
    login_name_xpath = '//*[@id="wrapper_body"]/div/div/form/div/span/strong/text()'
    texts = response.xpath(login_name_xpath).getall()
    return "".join(texts).find("错误") != -1

class QuotesSpider(scrapy.Spider):
    name = "quotes"
    visited_links = set('1')  # the first page will always be crawled.
    config = {}

    def start_requests(self):
        urls = [
            'http://fund.sciencenet.cn/login',
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        try:
            with open('./config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except:
            self.logger.error('Please provide a ./config.json file!')
            raise Exception("No config.json file provided!")

        return scrapy.FormRequest.from_response(
            response,
            formdata={'phone': self.config["手机号码"],
                      'password': self.config["密码"]},
            callback=self.after_login
        )

    def construct_search_url(self):
        fuzzy_search = ""
        if self.config["模糊查询"] == "开启":
            fuzzy_search = "&match=1"
        url = 'http://fund.sciencenet.cn/search?name={name}&yearStart={yearStart}&yearEnd={yearEnd}&subject={subject}&category={category}&fundStart={fundStart}&fundEnd={fundEnd}&submit=list'.format(
                name=self.config["查询项目名称"],
                yearStart=self.config['批准年度开始'],
                yearEnd=self.config['批准年度结束'],
                subject=self.config['学科分类'],
                category=self.config['项目类别'],
                fundStart=self.config['fundStart'],
                fundEnd=self.config['fundEnd']) + fuzzy_search
        return url
    def after_login(self, response):
        # TODO: the authentication check is never reached if the login is failed. The reason is when the login fails, after_login will never call which is due to scrapy duplicates filter.
        if authentication_failed(response):
            self.logger.error("Login failed")
            raise Exception("user name and password are not correct!")
        self.logger.info(
            'Crawling for name = {}...'.format(self.config["查询项目名称"]))
        return scrapy.Request(
            self.construct_search_url(),
            callback=self.after_search
        )

    def iter_pages(self, response):
        def is_page_link(link):
            return re.search(urllib.parse.quote(self.config["查询项目名称"]), link) != None
        pages_xpath = '//*[@id="page_button"]/span/a/@href'
        links = response.xpath(pages_xpath).getall()
        return filter(is_page_link, links)

    def after_search(self, response):
        for item in self.collect_items(response):
            yield item
        for link in self.iter_pages(response):
            if not self.has_visited(link):
                self.visited_links.add(self.normalize(link))
                yield response.follow(link, callback=self.after_search)

    def normalize(self, link):
        pat = re.compile(r'page=(?P<page>\d{1,4})')
        m = pat.search(link)
        return m.group('page') if m else ''

    def has_visited(self, link):
        normalize_link = self.normalize(link)
        return normalize_link in self.visited_links

    def collect_items(self, response):
        item_xpath = '//*[@id="resultLst"]/div[@class="item"]'
        for i in response.xpath(item_xpath):
            yield self.get_item(i)

    def get_item(self, item):
        texts = item.xpath('p[@class="t"]/a//text()').getall()
        author = item.xpath('div[@class="d"]/p/span[1]/i/text()').get()
        number = item.xpath('div[@class="d"]/p/b/text()').get()
        research_type = item.xpath('div[@class="d"]/p/i/text()').get()
        department = item.xpath('div[@class="d"]/p/span[2]/i/text()').get()
        year = item.xpath('div[@class="d"]/p/span[3]/b/text()').get()
        money = item.xpath('div[@class="d"]/p[2]/span[1]/b/text()').get()
        keywords = item.xpath('div[@class="d"]/p[2]/span[2]/i/text()').getall()

        return {
            "name": "".join(map(lambda s: s.strip(), texts)),
            "author": author,
            "number": number,
            "department": department,
            "research_type": research_type,
            "year": year,
            "money": money,
            "keywords": "".join(map(lambda s: s.strip(), keywords)),
        }
