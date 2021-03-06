import sys
import asyncio, time, os, json

# 为什么使用aiomysql?一次使用异步 处处使用异步
import aiomysql
import logging;logging.basicConfig(level=logging.INFO)


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
async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs


# 封装insert\update\delete三个语句
# 因为这3种SQL的执行都需要相同的参数，注意：语句格式并不一样。以及返回一个整数表示影响的行数：
async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected


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

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


# 定义USER类来操作/对应数据表USERS


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
        attrs['__mappings__'] = mappings#dict
        # 保存表名
        attrs['__table__'] = table_name  # 这里的tablename并没有转换成反引号的形式
        # 保存主键名称
        attrs['__primary_key__'] = primaryKey
        # 保存主键外的属性名，不包括属性名对应的属性值
        attrs['__fields__'] = fields
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s` ' % (primaryKey, ', '.join(escaped_fields), table_name)
        attrs['__insert__'] = 'insert into  `%s` (%s, `%s`) values (%s) ' % (table_name, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (table_name, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name, primaryKey)
        return type.__new__(cls, name, bases,attrs)  # 这儿也可以写成super(ModelMetaclass,cls).__new__(cls, name, bases, attrs)


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

    def getValue(self, key):
        return getattr(self, key, None)
        # getattr()是内置函数。返回self这个对象的key属性对应值，如果没有这个，就返回默认值None.

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    # 类方法有类变量cls传入，从而可以用cls做一些相关的处理。
    # 并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类
    #更高级的查找，考虑oderBy以及limit
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
    #类方法。返回的是……
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
    #attrs['__select__'] = 'select `%s`, %s from `%s` ' % (primaryKey, ', '.join(escaped_fields), table_name)
    # 这儿的cls有点儿类似实例方法的self，不需要显示传值，值当前类对象本身。
    #由类自身调用。根据primary_key查找，因为primary_key的唯一性，所以只返回一行记录。
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
    # # __select__:'select `%s`, %s from `%s` ' % (primaryKey, ', '.join(escaped_fields), table_name)
    #这儿的cls有点儿类似实例方法的self，不需要显示传值，指当前类对象本身。
    # 根据WHERE条件查找；name="xxx",email="xxx"。返回的是对应的一行或多行行记录
    def findAll(cls, **kw):
        rs = []
        if len(kw) == 0:#kw为0的话相当于查找全部(查找条件为空)
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

    # attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name, primaryKey
    @asyncio.coroutine
    def save(self):
        #实例方法，先新建一个实例eg：User1=User(……),然后用该实例调用save()，实际上，就是调用execute()执行力insert操作
        args = list(map(self.getValueOrDefault, self.__fields__))
        #print('save:%s' % args)
        args.append(self.getValueOrDefault(self.__primary_key__))
        print('save:%s' % args)
        #print(self.__insert__)
        #print(self.__fields__)
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            print(self.__insert__)
            logging.warning('failed to insert record: affected rows: %s' % rows)

    #终于搞懂update()怎么工作了。实例方法，由实例调用；
    #新建一个实例User_new=User(name="new_name"……id="old_id")：其实这儿要把表中的7个字段都写进来。
    # 就算你只想改变其中一个字段，另外6个都需要传旧值进来；
    #这样其实没法再实际中应用。这儿还需要优化。
    # attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (table_name, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
    @asyncio.coroutine
    def update(self):  # 修改数据库中已经存入的数据
        args = list(map(self.getValue, self.__fields__))  # 获得的value是User2实例的属性值，也就是传入的name，email，password值
        args.append(self.getValue(self.__primary_key__))
        print('update:%s' % args)
        rows = yield from execute(self.__update__, args)
        print(rows)
        if rows != 1:
            logging.warning('failed to update record: affected rows: %s' % rows)

    #实例方法。由实例调用，创建实例的时候只需要传入primary_key 也即是id的值
    # attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name, primaryKey)
    @asyncio.coroutine
    def delete(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warning('failed to delete by primary key: affected rows: %s' % rows)

