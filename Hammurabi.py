import random

class Hammurabi:
    def __init__(self):
        self.rand = random.Random()

    # --- INPUT HELPER METHODS (Your logic) ---
    def askHowManyAcresToBuy(self, price, bushels):
        while True:
            try:
                acres = int(input(f"How many acres do you wish to buy? (Price: {price}): "))
                if acres < 0: print("You cannot buy negative.")
                elif acres * price > bushels: print(f"You only have {bushels} bushels!")
                else: return acres
            except ValueError: print("Enter a whole number.")

    def askHowManyAcresToSell(self, acresOwned):
        while True:
            try:
                acres = int(input(f"How many acres do you wish to sell? (You own: {acresOwned}): "))
                if acres < 0: print("You cannot sell negative.")
                elif acres > acresOwned: print(f"You only own {acresOwned}!")
                else: return acres
            except ValueError: print("Enter a whole number.")

    def askHowMuchGrainToFeedPeople(self, bushels):
        while True:
            try:
                feed = int(input(f"How much grain to feed people? (Total: {bushels}): "))
                if feed < 0: print("Cannot feed negative.")
                elif feed > bushels: print("You don't have that much.")
                else: return feed
            except ValueError: print("Enter a whole number.")

    def askHowManyAcresToPlant(self, acresOwned, population, bushels):
        while True:
            try:
                plant = int(input(f"How many acres to plant? (Max: {acresOwned}): "))
                if 0 <= plant <= acresOwned and plant <= population * 10 and plant * 0.5 <= bushels:
                    return plant
                print("Check your population, land, or grain limits!")
            except ValueError: print("Enter a whole number.")

    # --- MAIN GAME LOOP ---
    def playGame(self):
        grain = 2800
        population = 100
        acresOwned = 1000
        costOfLand = 19
        year = 1

        print("Congratulations, Hammurabi! You have been elected for a 10-year term.")

        while year <= 10:
            print(f"\n--- Year {year} ---")
            print(f"Pop: {population} | Grain: {grain} | Land: {acresOwned} | Price: {costOfLand}")

            # 1. Buying/Selling
            acresToBuy = self.askHowManyAcresToBuy(costOfLand, grain)
            if acresToBuy > 0:
                grain -= (acresToBuy * costOfLand)
                acresOwned += acresToBuy
            else:
                acresToSell = self.askHowManyAcresToSell(acresOwned)
                grain += (acresToSell * costOfLand)
                acresOwned -= acresToSell

            # 2. Feeding
            grainToFeed = self.askHowMuchGrainToFeedPeople(grain)
            grain -= grainToFeed

            # 3. Planting
            acresToPlant = self.askHowManyAcresToPlant(acresOwned, population, grain)
            grain -= int(acresToPlant * 0.5)

            # 4. End of Year Processing (Basic Logic)
            harvest_yield = random.randint(1, 6)
            harvest = acresToPlant * harvest_yield
            grain += harvest
            
            # Simple starvation (20 bushels per person)
            starved = max(0, population - (grainToFeed // 20))
            population -= starved
            
            if starved > population * 0.45:
                print(f"You were impeached! {starved} people starved.")
                break

            # Update for next year
            costOfLand = random.randint(17, 26)
            year += 1

        print("Final Report: Your reign has ended.")

if __name__ == "__main__":
    game = Hammurabi()
    game.playGame()
