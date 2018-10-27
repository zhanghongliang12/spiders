# -*- coding: utf-8 -*-
import json
import re
import random
import scrapy
from scrapy import Request

from xpc.items import CopyrightItem, ComposerItem, CommentItem, PostItem

strip = lambda x: x.strip() if x else ''


def convert_int(s):
    if s:
        return int(s.replace(',', ''))
    return 0


ci = convert_int
cookies = {
    'Authorization': 'D0A7850E249EC0AE6249EC4345249ECB535249EC7C4535999D64',
}


def gen_sessionid():
    letters = [chr(i) for i in range(97, 123)]
    letters.extend([str(i) for i in range(10)])
    return ''.join(random.choices(letters, k=26))


class DiscoverySpider(scrapy.Spider):
    name = 'discovery'
    allowed_domains = ['xinpianchang.com', 'openapi-vtom.vmovier.com']
    start_urls = ['http://www.xinpianchang.com/channel/index/sort-like?from=tabArticle']
    page_counts = 0

    def parse(self, response):
        if response.text.find('系统繁忙') != -1:
            print('@' * 50,'系统繁忙', '@' * 50)
        else:
            self.page_counts += 1
            """解析列表页面"""
            # 视频详情页的url模板
            url = 'http://www.xinpianchang.com/a%s?from=ArticleList'
            # 选择出每一个视频节点对象
            post_list = response.xpath('//ul[@class="video-list"]/li')
            for post in post_list:
                # 视频ID
                pid = post.xpath('./@data-articleid').extract_first()
                #
                request = Request(url % pid, callback=self.parse_post)
                # 把Pid和缩略图传给回调函数
                request.meta['pid'] = pid
                request.meta['thumbnail'] = post.xpath('./a/img/@_src').get()
                # from scrapy.shell import inspect_response
                # inspect_response(response, self)
                # break
                yield request

        if self.page_counts > 90:
            cookies['PHPSESSID'] = gen_sessionid()
            self.page_counts = 0
        next_pages = response.xpath('//div[@class="page"]/a/@href').extract()
        for page in next_pages:
            yield response.follow(page, cookies=cookies)

    def parse_post(self, response):
        """解析视频详情页"""
        # 取出上一个函数传递的参数
        pid = response.meta['pid']
        post = PostItem()
        post['pid'] = pid
        # 缩略图
        post['thumbnail'] = response.meta['thumbnail']
        # 标题
        post['title'] = response.xpath(
            '//div[@class="title-wrap"]/h3/text()').extract_first()
        # 分类信息
        cates = response.xpath(
            '//span[contains(@class, "cate")]/a/text()').extract()
        post['category'] = '-'.join([cate.strip() for cate in cates])
        # 发布时间
        post['created_at'] = response.xpath(
            '//span[contains(@class, "update-time")]/i/text()').get()
        # 播放次数
        post['play_counts'] = response.xpath(
            '//i[contains(@class, "play-counts")]/@data-curplaycounts').get()
        # 点赞次数
        post['like_counts'] = response.xpath(
            '//span[contains(@class, "like-counts")]/@data-counts').get()
        # 描述信息
        post['description'] = strip(response.xpath(
            '//p[contains(@class, "desc")]/text()').get())
        # 提取视频的vid,这个是请求视频源文件地址的关键参数
        vid, = re.findall(r'vid: \"(\w+)\",', response.text)
        # 请求视频信息接口，把vid参数代入进去
        video_url = 'https://openapi-vtom.vmovier.com/v3/video/%s?expand=resource,resource_origin?'
        request = Request(video_url % vid, callback=self.parse_video)
        request.meta['post'] = post
        yield request
        # 请求评论接口，注意ajax=1时返回Html，=0或者不写时返回json
        comment_url = 'http://www.xinpianchang.com/article/filmplay/ts-getCommentApi?id=%s&ajax=0&page=1'
        request = Request(comment_url % pid, callback=self.parse_comment)
        yield request

        # 请求用户页面
        composer_url = 'http://www.xinpianchang.com/u%s?from=articleList'
        # 选择出所有的包含作者信息的节点
        composer_list = response.xpath('//div[@class="user-team"]//ul[@class="creator-list"]/li')
        for composer in composer_list:
            # 作者ID
            cid = composer.xpath('./a/@data-userid').get()
            request = Request(composer_url % cid, callback=self.parse_composer)
            request.meta['cid'] = cid
            yield request
            # 保存作者和视频之间的对应关系
            cr = CopyrightItem()
            # 用cid和Pid组合起来作为主键
            cr['pcid'] = '%s_%s' % (cid, pid)
            cr['cid'] = cid
            cr['pid'] = pid
            # 不同作者在不同作品里担任的角色也不一样，所以也要保存起来
            cr['roles'] = composer.xpath('.//span[contains(@class, "roles")]/text()').get()
            yield cr

    def parse_video(self, response):
        """解析视频接口"""
        post = response.meta['post']
        resp = json.loads(response.text)
        # 视频源文件地址
        post['video'] = resp['data']['resource']['default']['url']
        # 视频预览图地址
        post['preview'] = resp['data']['video']['cover']
        yield post

    def parse_comment(self, response):
        """解析评论接口"""
        resp = json.loads(response.text)
        composer_url = 'http://www.xinpianchang.com/u%s?from=articleList'
        for c in resp['data']['list']:
            comment = CommentItem()
            comment['commentid'] = c['commentid']
            comment['pid'] = c['articleid']
            comment['content'] = c['content']
            comment['created_at'] = c['addtime_int']
            comment['cid'] = c['userInfo']['userid']
            comment['uname'] = c['userInfo']['username']
            comment['avatar'] = c['userInfo']['face']
            comment['like_counts'] = c['count_approve']
            # 如果有reply字段，说明本条评论是回复的另一条评论
            if c['reply']:
                # 把reply字段设置为被回复那条评论的ID
                comment['reply'] = c['reply']['commentid']
            yield comment

            request = Request(composer_url % comment['cid'], callback=self.parse_composer)
            request.meta['cid'] = comment['cid']
            yield request
        # 判断是否还需要翻页
        next_page = resp['data']['next_page_url']
        if next_page:
            yield response.follow(next_page, self.parse_comment)

    def parse_composer(self, response):
        """解析作者主页"""
        banner = response.xpath('//div[@class="banner-wrap"]/@style').get()
        composer = ComposerItem()
        composer['cid'] = response.meta['cid']
        composer['banner'], = re.findall(
            r'background-image:url\((.+?)\)', banner)
        composer['avatar'] = response.xpath(
            '//span[@class="avator-wrap-s"]/img/@src').get()
        composer['name'] = response.xpath(
            '//p[contains(@class, "creator-name")]/text()').get()
        composer['intro'] = response.xpath(
            '//p[contains(@class, "creator-desc")]/text()').get()
        composer['like_counts'] = ci(response.xpath(
            '//span[contains(@class, "like-counts")]/text()').get())
        composer['fans_counts'] = response.xpath(
            '//span[contains(@class, "fans-counts")]/@data-counts').get()
        composer['follow_counts'] = ci(response.xpath(
            '//span[@class="follow-wrap"]/span[2]/text()').get())
        # 取类名中包含icon-location的span的相邻的下一个span内的文本
        composer['location'] = response.xpath(
            '//span[contains(@class, "icon-location")]/'
            'following-sibling::span[1]/text()').get() or ''
        composer['career'] = response.xpath(
            '//span[contains(@class, "icon-career")]/'
            'following-sibling::span[1]/text()').get() or ''
        yield composer


