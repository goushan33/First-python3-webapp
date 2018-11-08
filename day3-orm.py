import sys
import asyncio, time, os, json

# 为什么使用aiomysql?一次使用异步 处处使用异步
import aiomysql
import logging;

logging.basicConfig(level=logging.INFO)


# logging级别有：debug\info\warning\error\critical,level从10到50.
# 默认的级别是warning,低于warning就不会输出到控制台，高于warning的message输出的控制台
# 手动更改logging级别到info:logging.basicConfig(level=logging.INFO)


def log(sql, args=()):
    logging.info('SQL:%s' % sql)


# 创建一个全局的连接池，每个HTTP请求都可以从连接池中直接获取数据库连接。
# 连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务：
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    # dict有个get方法，接受两个参数，如果dict中有参数1这个key，则返回对应的value值，如果没有
    # 这个key，则返回参数2.例如，如果kw里有host，则返回对应的value,否则返回localhost。
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )



@asyncio.coroutine
def destory_pool():
    global __pool
    if __pool is not None:
        __pool.close()  # close()不是一个coroutine
        yield from __pool.wait_closed()  # wait_closed()是一个coroutine


# select函数执行SELECT语句
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql)  # 前面定义的log()只接受一个参数
    global __pool
    # 有了连接池，现在应该是为某个连接建立游标
    # 1、这儿用yield from 调用子协程，并直接返回调用结果
    # 2、yield from 从连接池中返回一个连接（前提是已经建立了连接池）
    with (yield from __pool)as conn:  # 3、用with 语句确保会关闭连接
        curs = yield from conn.cursor(aiomysql.DictCursor)  # A cursor which returns results as a dictionary.
        yield from curs.execute(sql.replace('?', '%s'), args)
        if size:
            rs = yield from curs.fetchmany(size)  # 一次性返回size条查询结果，结果是个list，元素为tuple。因为是select，所以不用提交事务
        else:
            rs = yield from curs.fetchall()  # 一次性返回所以的查询结果
        yield from curs.close()  # 关闭游标，不用手动关闭connection，因为connection在with语句里
        logging.info('%s rows has been returned' % len(rs))
    return rs  # 返回查询结果，元素为tuple的list


# 封装insert\update\delete三个语句
# 因为这3种SQL的执行都需要相同的参数，注意：语句格式并不一样。以及返回一个整数表示影响的行数：
@asyncio.coroutine
def execute(sql, args, autocommit=True):  # 有必要写autocommit=True吗？存疑
    log(sql)
    global __pool
    with (yield from __pool) as conn:
        try:
            curs = yield from conn.cursor()
            yield from execute(sql.replace('?', '%s'), args)
            yield from conn.commit()
            # 因为execute类型sql操作返回结果只有行号
            affected_lines = curs.rowcount
            yield from curs.close()  # 手动关闭cursor
            print('affected_lines:%s' % affected_lines)
        except BaseException as e:
            raise
        return affected_lines


# 这个函数主要是把查询字段计数 替换成sql识别的?
# 比如说：insert into  `User` (`password`, `email`, `name`, `id`) values (?,?,?,?)  看到了么 后面这四个问号
def create_args_string(num):
    lol = []
    for n in range(num):
        lol.append('?')
    return (','.join(lol))


# ORM全称“Object Relational Mapping”，即对象-关系映射，就是把关系数据库的一行映射为一个对象，也就是一个类对应一个表，这样，写代码更简单，不用直接操作SQL语句。
# 要编写一个ORM框架，所有的类都只能动态定义，因为只有使用者才能根据表的结构定义出对应的类来。
# 定义Field类，负责保存数据库表的字段名和字段类型
class Field(object):
    # 表的字段包含字段名字、类型、是否主键以及默认值
    def __init__(self, name, colum_type, primary_ket, default):
        self.name = name
        self.colum_type = colum_type
        self.primary_key = primary_ket
        self.default = default

    def __str__(self):
        return "<%s,%s:%s>" % (self.__class__.__name__, self.name, self.colum_type)


# 定义5种数据类型,先定义2种
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=None):
        super().__init__(name, 'int', primary_key, default)


class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


# 定义USER类来操作/对应数据表USER


# 接下来定义Model类，先定义它的元类ModelMetaclass.
# 我们在这个元类ModelMetaclass中定义了所有Model基类的子类实现的操作
# metaclass是类的模板，所以必须从`type`类型派生：
class ModelMetaclass(type):  # 请记住，type实际上是一个类
    # __new__控制__init__的执行，__new__是在__new__之前被调用的特殊方法
    # __new__是用来创建对象并返回之的方法，在这儿是创建类这种对象
    # __new__()方法接收到的参数依次是：
    # cls:类似于self一样，因为类方法的第一个参数总是表示当前的实例；
    # name:要创建的类的名字；
    # bases:要创建的类继承的父类集合；
    # attrs:要创建的类的属性集合
    def __new__(cls, name, bases, attrs):
        # 排除掉Model类本身:为什么要排除掉Model类呢？
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        table_name = attrs.get('__table__', None) or name  # 这儿应该能看出来attrs应该是个dict
        logging.info('found table:%s(table:%s)' % (name, table_name))  # 找到了数据库表名和即将创建的类名的映射
        # 获取所有的Field和主键名
        mappings = dict()
        fields = []  # 保存除开主键外的属性名
        primaryKey = None
        # 在当前类（比如User）中查找定义的类的所有属性
        for k, v in attrs.items():
            if isinstance(v, Field):  # 这样理解：v是StringField、IntField等类
                logging.info('Found mapping %s==>%s' % (k, v))  # 找到一对映射
                mappings[k] = v  # 从dict attrs中筛选出value类型为Field的属性，保存在dict mappings里面
                if v.primary_key:
                    logging.info('found primary key %s' % k)

                    if primaryKey:  # 初始的primaryKey为0，如果这儿非0，说明已经被赋过值了，说明已经找到一个主键了
                        raise RuntimeError('Duplicated key for field')  # 一个表只能有一个主键
                    primaryKey = k
                else:
                    fields.append(k)  # 把非主键属性存入到fileds
        if not primaryKey:  # 遍历完一个表的字段（也就是遍历完新类所有的属性后），如果没有找到主键也会报错
            raise RuntimeError('primary key not found')
        for k in mappings.keys():
            attrs.pop(k)  # 为什么要删除这个类属性？

        # 保存除主键外的属性为列表形式
        # 将除主键外的其他属性变成`id`, `name`这种形式
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        # 保存属性和列的映射关系。为一个类动态添加属性、方法，这就是动态语言
        attrs['__mappings__'] = mappings
        # 保存表名
        attrs['__table__'] = table_name  # 这里的tablename并没有转换成反引号的形式
        # 保存主键名称
        attrs['__primary_key__'] = primaryKey
        # 保存主键外的属性名，不包括属性名对应的属性值
        attrs['__fields__'] = fields
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s` ' % (primaryKey, ', '.join(escaped_fields), table_name)
        attrs['__insert__'] = 'insert into  `%s` (%s, `%s`) values (%s) ' % (
        table_name, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (
        table_name, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name, primaryKey)
        return type.__new__(cls, name, bases,
                            attrs)  # 这儿也可以写成super(ModelMetaclass,cls).__new__(cls, name, bases, attrs)


# 基于字典查询形式
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
    # setattr()、getattr()动态地给Model类增加属性或者类方法
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("'Model' object have no attribution: %s" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getvalue(self, key):
        return getattr(self, key, None)  # getattr()是内置函数。返回self这个对象的key属性对应值，如果没有这个，就返回默认值None.

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    # 类方法有类变量cls传入，从而可以用cls做一些相关的处理。并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类
    @classmethod
    @asyncio.coroutine
    def find_all(cls, where=None, args=None, **kw):
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []

        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value : %s ' % str(limit))

        rs = yield from select(' '.join(sql), args)  # 返回的rs是一个元素是tuple的list
        return [cls(**r) for r in rs]  # **r 是关键字参数，构成了一个cls类的列表，其实就是每一条记录对应的类实例

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        '''find number by select and where.'''
        sql = ['select %s __num__ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['__num__']

    @classmethod
    @asyncio.coroutine
    def find(cls, primarykey):
        '''find object by primary key'''
        # rs是一个list，里面是一个dict
        # __select__:'select `%s`, %s from `%s` ' % (primaryKey, ', '.join(escaped_fields), table_name)
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [primarykey], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])  # 返回一条记录，以dict的形式返回，因为cls的夫类继承了dict类

    @classmethod
    @asyncio.coroutine
    def findAll(cls, **kw):  # 根据WHERE条件查找
        rs = []
        if len(kw) == 0:
            rs = yield from select(cls.__select__, None)
        else:
            args = []
            values = []
            for k, v in kw.items():
                args.append('%s=?' % k)
                values.append(v)
            print('%s where %s ' % (cls.__select__, ' and '.join(args)), values)
            rs = yield from select('%s where %s ' % (cls.__select__, ' and '.join(args)), values)
        return rs

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        print('save:%s' % args)
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            print(self.__insert__)
            logging.warning('failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):  # 修改数据库中已经存入的数据
        args = list(map(self.getValue, self.__fields__))  # 获得的value是User2实例的属性值，也就是传入的name，email，password值
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warning('failed to update record: affected rows: %s' % rows)


    @asyncio.coroutine
    def delete(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warning('failed to delete by primary key: affected rows: %s' % rows)


class User(Model):  # Model基类还没定义
    __table__ = 'users'
    # 一个类的属性对应一个数据表的列
    id = IntegerField('id',primary_key=True)
    name = StringField('name')


if __name__ == "__main__":
    class User2(Model):
        id = IntegerField('id', primary_key=True)
        name = StringField('name')
        email = StringField('email')
        password = StringField('password')


    loop = asyncio.get_event_loop()  # 创建异步事件句柄


    # 创建实例
    def test():
        yield from create_pool(loop=loop, host='localhost', port=3306, user='root', password='password', db='test')
        user = User2(id=2, name='Tom', email='slysly759@gmail.com', password='12345')
        yield from user.save()
        r = yield from User2.findAll()
        print(r)
        r=yield from User2.find()
        print(r)
        yield from destory_pool()



    loop.run_until_complete(test())
    loop.close()
    if loop.is_closed():
        sys.exit(0)