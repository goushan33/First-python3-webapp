import day3_orm
from day4_models import User,Blog,Comment
import asyncio,sys
import logging;logging.basicConfig(level=logging.INFO)

if __name__=="__main__":
    loop = asyncio.get_event_loop()

    # 创建实例

    async def test():
        await day3_orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
        #user5 = User(id="001541857400551f985c56287cf4cdeae93303b5582e875000")
        #yield from user5.save()
        #res=yield from user1.findAll()
        #yield from User.find("001541855628594e31396dec7ac4324982a980168143434360")
        #yield from User.findAll(name="Test_user4")
        #yield from User.findAll(name="Test_user4",email="test4@example.com")
        #await User.findAll()
        #yield from User.find_all(where="email=test4@example.com",args=None,limit=2)

        await day3_orm.destory_pool()

    loop.run_until_complete(test())
    loop.close()
    if loop.is_closed():
        sys.exit(0)