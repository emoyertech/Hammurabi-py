import random

class Hammurabi:
    def __init__(self):
        self.rand = random.Random()

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
    
    def plague_deaths(population):
        if random.random() < 0.15:
            return population // 2
        return 0

    def starvation_deaths(population, bushels_fed):
        needed = population * 20
        if bushels_fed >= needed:
            return 0
        return population - (bushels_fed // 20)

    def uprising(population, starved):
        return starved > (population * 0.45)

    def immigrants(population, acres_owned, grain_in_storage):
        return (20 * acres_owned + grain_in_storage) // (100 * population) + 10

    def harvest(acres_planted):
        yield_per_acre = random.randint(1, 6)
        return yield_per_acre * acres_planted, yield_per_acre

    def grain_eaten_by_rats(bushels):
        if random.random() < 0.40:
            percentage = random.uniform(0.1, 0.3)
            return int(bushels * percentage)
        return 0

    def new_cost_of_land():
        return random.randint(17, 23)

    def print_summary(year, population, starved, immigrants, deaths, harvest_yield, rats_ate, bushels, acres, land_cost):
        print(f"\n--- Year {year} Report ---")
        if deaths > 0: print(f"A plague killed {deaths} people.")
        print(f"{starved} people starved.")
        print(f"{immigrants} people came to the city.")
        print(f"The harvest was {harvest_yield} bushels per acre.")
        print(f"Rats ate {rats_ate} bushels.")
        print(f"Population: {population} | Storage: {bushels} | Acres: {acres}")
        print(f"Land is trading at {land_cost} bushels per acre.")

    def final_summary(population, acres, total_starved):
        acres_per_person = acres / population
        print("\n=== FINAL GAME STATS ===")
        print(f"Total Starved over 10 years: {total_starved}")
        print(f"Acres per person: {acres_per_person:.2f}")
    
        if total_starved > 200 or acres_per_person < 7:
            print("The people are glad to see you go. You were a harsh ruler.")
        else:
            print("You have ruled wisely! The city prospers.")

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
