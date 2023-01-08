import pywikibot

from src.main import NPMBot, site

if __name__ == "__main__":
    bot = NPMBot()
    # Testing
    if site.code == "test":
        item = pywikibot.ItemPage(site, "Q227512")
        bot.process(bot.run_item(item), item)
        while bot.queue:
            item = pywikibot.ItemPage(site, bot.queue.popleft())
            bot.process(bot.run_item(item), item)
    else:
        bot.run()
