import sys
import asyncio,time,os,json

# 为什么使用aiomysql?一次使用异步 处处使用异步
import aiomysql
import logging;logging.basicConfig(level=logging.INFO)
#logging级别有：debug\info\warning\error\critical,level从10到50.
#默认的级别是warning,低于warning就不会输出到控制台，高于warning的message输出的控制台
#手动更改logging级别到info:logging.basicConfig(level=logging.INFO)


def log(sql,args=()):
    logging.info('SQL:%s'%sql)

#创建一个全局的连接池，每个HTTP请求都可以从连接池中直接获取数据库连接。
#连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务：
@asyncio.coroutine
def creat_pool(loop,**kw):#**dict是一个dict,关键字参数，实现‘可选’功能
    logging.info('create database connection pool……')
    global _pool
    _pool=yield from aiomysql.creat_pool(
#dict有个get方法，接受两个参数，如果dict中有参数1这个key，则返回对应的value值，如果没有
#这个key，则返回参数2.例如，如果kw里有host，则返回对应的value,否则返回localhost。
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop
    )


@asyncio.coroutine
def destory_pool():
    global _pool
    if _pool is not None:
        _pool.close()#close()不是一个coroutine
        yield from _pool.wait_closed()#wait_closed()是一个coroutine


#select函数执行SELECT语句
@asyncio.coroutine
def select(sql,args,size=None):
    log(sql,args)
    global _pool
    #有了连接池，现在应该是为某个连接建立游标
    #1、这儿用yield from 调用子协程，并直接返回调用结果
    #2、yield from 从连接池中返回一个连接（前提是已经建立了连接池）
    with (yield from _pool)as conn:#3、用with 语句确保会关闭连接
        curs=yield from conn.cursor(aiomysql.DictCursor)#A cursor which returns results as a dictionary.
        yield from curs.execute(sql.replace('?','%s'),args)
        if size:
            rs=yield from curs.fetchmany(size)#一次性返回size条查询结果，结果是个list，元素为tuple。因为是select，所以不用提交事务
        else:
            rs=yield from curs.fetchall()#一次性返回所以的查询结果
        yield from curs.close()#关闭游标，不用手动关闭connection，因为connection在with语句里
        logging.info('%s rows has been returned'%len(rs))
    return rs#返回查询结果，元素为tuple的list


#封装insert\update\delete三个语句
#因为这3种SQL的执行都需要相同的参数，注意：语句格式并不一样。以及返回一个整数表示影响的行数：


