# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html
import pymysql
class MysqlPipeline(object):
    def __init__(self):
        self.conn = None
        self.cur = None
    def open_spider(self, spider):
        self.conn = pymysql.connect(
            host='127.0.0.1',
            port=3306,
            db='xpc_1810',
            user='root',
            password='123456',
            charset='utf8mb4',
        )
        self.cur = self.conn.cursor()

    def close_spider(self, spider):
        self.cur.close()
        self.conn.close()

    def process_item(self, item, spider):
        cols = item.keys()
        values = list(item.values())
        sql = "insert into `{}` ({}) values ({}) on duplicate key update {}".format(
            item.table_name,
            ','.join(['`%s`' % col for col in cols]),
            ','.join(['%s'] * len(values)),
            ','.join(['`{}`=%s'.format(col) for col in cols])

        )
        self.cur.execute(sql, values * 2)
        self.conn.commit()
        return item
















