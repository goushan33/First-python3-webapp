import day3_orm
from day4_models import User,Blog,Comment
import asyncio,sys
import logging;logging.basicConfig(level=logging.INFO)
import day6_config

if __name__=="__main__":
    loop = asyncio.get_event_loop()

    # 创建实例

    async def test():
        await day3_orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
        #user6 = User(name='20190409TEST',email='20190409@qq.com',passwd='20190409',admin=0,image=' about:blank')
        #await user6.save()
        #await user6.findAll()
        #new_user6 = User(id='001554793624630f8288d2d088f415c8c51d903f8b7aa64000 ',created_at=1554793624.63017,name='20190409TEST', email='new_email', passwd='20190409', admin=0, image=' about:blank')
        #await new_user6.update()
        #await user1.findAll()
        #await User.find("001541855628594e31396dec7ac4324982a980168148e43000")
        #await User.find_all(orderBy='created_at')
        #await User.findAll(name="Test_user4",email="test4@example.com")
        #await User.findAll()
        #await User.find_all(where="email=test4@example.com",args=None,limit=2)
        #await User.findNumber('count(id)')
        user=await User.findAll(email='test4@example.com ')
        #print(type(user))#a list contains a dict
        user=user[0]
        userDict=day6_config.toDict(user)
        print(userDict.name)


        await day3_orm.destory_pool()

    loop.run_until_complete(test())
    loop.close()
    if loop.is_closed():
        sys.exit(0)