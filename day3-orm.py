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
    log(sql)#前面定义的log()只接受一个参数
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
@asyncio.coroutine
def execute(sql,args,autocommit=True):#有必要写autocommit=True吗？存疑
    log(sql)
    global _pool
    with (yield from _pool) as conn:
        try:
            curs=yield from conn.cursor()
            yield from execute(sql.replace('?','%s'),args)
            yield from conn.commit()
            # 因为execute类型sql操作返回结果只有行号
            affected_lines=curs.rowcount
            yield from curs.close()#手动关闭cursor
            print('affected_lines:%s'%affected_lines)
        except BaseException as e:
            raise
        return affected_lines



# 这个函数主要是把查询字段计数 替换成sql识别的?
# 比如说：insert into  `User` (`password`, `email`, `name`, `id`) values (?,?,?,?)  看到了么 后面这四个问号
def create_args_string(num):
    lol=[]
    for n in range(num):
        lol.append('?')
    return (','.join(lol))


#定义Field类，负责保存数据库表的字段名和字段类型
class Field(object):
    #表的字段包含字段名字、类型、是否主键以及默认值
    def __init__(self,name,colum_type,primary_ket,default):
        self.name=name
        self.colum_type=colum_type
        self.primary_key=primary_ket
        self.default=default
    def __str__(self):
        return "<%s,%s,%s>"%(self.__class__.__name__,self.name,self.colum_type,self.primary_key,self.default)

#定义5种数据类型,先定义2种
class IntegerField(Field):
    def __init__(self,name=None,primary_key=False,default=None):
        super().__init__(name,'int',primary_key,default)

class StringField(Field):
    def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
        super().__init__(name,ddl,primary_key,default)


#定义USER类来操作/对应数据表USER
class User(Model):#Model基类还没定义
    __table__='users'
    #一个类的属性对应一个数据表的列
    id=IntegerField('id')
    name=StringField('name')




#接下来定义Model类，先定义它的元类ModelMetaclass.
#我们在这个元类ModelMetaclass中定义了所有所有Model基类的子类实现的操作
#metaclass是类的模板，所以必须从`type`类型派生：
class ModelMetaclass(type):
# __new__控制__init__的执行，所以在其执行之前,这儿没懂
#__new__()方法接收到的参数依次是：
# cls:当前准备创建的类的对象；
# name:类的名字；
# bases:类继承的父类集合；
# attrs:类的方法集合,这个说成类的属性集合是不是更好呢。
    def __new__(cls, name, bases,attrs):
        #Model类本身:
        if name=='Model':
            return type.__new__(cls,name,bases,attrs)
        table_name=attrs.get('__table__',None) or name#这儿应该能看出来attrs应该是个dict
        logging.info('found table:%s(table:%s)'%(name,table_name))
        #获取所有的Field和主键名
        mappings=dict()
        fields=[]#保存除开主键外的属性名
        primaryKey=None
        for k,v in attrs.items():
            if isinstance(v,Field):#是否可以理解v是一个field实例或者StringField实例
                logging.info('Found mapping %s==>%s'%(k,v))#找到一对映射
                mappings[k]=v#从dict attrs中筛选出value类型为Field的元素，保存在dict mappings里面
                if v.primary_key:
                    logging.info('found primary key %s'%k)

                    if primaryKey:#初始的primaryKey为0，如果这儿非0，说明已经被赋过值了，说明已经找到一个主键了
                        raise RuntimeError('Duplicated key for field')#一个表只能有一个主键
                    primaryKey=k
                else:
                    fields.append(k)#增加一个非主键属性
        if not primaryKey:#遍历完一个表的字段（也就是遍历完Field类所有的属性后），如果没有找到主键也会报错
            raise RuntimeError('primary key not found')
        for k in mappings.keys():
            attrs.pop(k)

        # 保存除主键外的属性为列表形式
        # 将除主键外的其他属性变成`id`, `name`这种形式
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        # 保存属性和列的映射关系
        attrs['__mappings__'] = mappings
        # 保存表名
        attrs['__table__'] = table_name  # 这里的tablename并没有转换成反引号的形式
        # 保存主键名称
        attrs['__primary_key__'] = primaryKey
        # 保存主键外的属性名
        attrs['__fields__'] = fields
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s` ' % (primaryKey, ', '.join(escaped_fields), table_name)
        attrs['__insert__'] = 'insert into  `%s` (%s, `%s`) values (%s) ' % (table_name, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (table_name, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name, primaryKey)
        return type.__new__(cls, name, bases, attrs)