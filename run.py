from src.main import NPMBot

if __name__ == "__main__":
    bot = NPMBot()
    bot.queue.appendleft("Q95972606")
    bot.run()
