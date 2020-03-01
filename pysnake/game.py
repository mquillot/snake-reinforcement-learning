# -*- coding: utf-8 -*-
# Created on Sun Feb 16 12:48:18 2020
# @author: arthurd


import numpy as np
import random as rd

try:
    import pygame
except ModuleNotFoundError:
    print("Module PyGame is not installed.")


from pysnake.enum import Item, Direction
from pysnake.grid import Cell, Grid
from pysnake.snake import Snake, save_snake, load_snake
from pysnake.windraw import WindowGame

from pysnake.gen.population import Population
from pysnake.nn.functional import softmax, relu, tanh, leaky_relu, linear

class Game:
    
    def __init__(self, shape=None, grid=None, seed=None):
        
        assert not (shape is None and grid is None), ('Cannot create a game without specifying at least shape.') 
        
        # Fix random numbers, use for debug mode
        self.seed = seed
        if not seed is None:
            np.random.seed(seed)
            rd.seed(seed)
        
        if grid is None:
            grid = Grid(shape)
            # Add borders to the grid
            grid.add_wall_borders()
        self.grid = grid
        self.shape = grid.shape

        self.snakes = []
        self.apples = []
        self.shape = shape
              
        
    def add_snake(self, snake=None, **kwargs):
        if snake is None:
            snake = Snake(self, **kwargs)
        else:
            snake.game = self
            snake.full_vision.grid = self.grid
        self.snakes.append(snake)
        self.grid.set_cell(*snake.body)
    
    
    def add_apple(self):
        apple = self.generate_apple()
        self.apples.append(apple)
        # Update the grid
        self.grid.set_cell(apple)
      
        
    def generate_apple(self):
               
        height, width = self.shape
        available_coord = []
        
        # Check the available cells
        for i in range(height):
            for j in range(width):
                cell = self.grid[i, j]
                # If the cell is empty, add it to the available cells list
                if cell.is_empty():
                    available_coord.append(cell.coord)
                    
        # Choose a position among all
        coord = rd.choices(available_coord)[0]
        apple = Cell(coord, Item.APPLE)
                
        return apple
        
    
    def clean(self):
        # Kill the snakes
        for snake in self.snakes:
            snake.kill()
        self.snakes = []     
        # Delete all apples
        for apple in self.apples:
            self.grid.set_empty(apple.coord)
        self.apples = []
        

    def start(self, snake=None, **kwargs):
        self.clean()
        self.add_snake(snake, **kwargs)
        self.add_apple()     
        snake.update()




class GameApplication:
    
    def __init__(self, config):

        # Main Game
        # ----
        self.board_size = eval(config.get('Game', 'board_size'))
        self.seed = eval(config.get('Game', 'seed'))
        self.game = Game(self.board_size, seed = self.seed)
        
        # WindowGame
        # ----------
        self.show = eval(config.get('WindowGame', 'render'))
        # Render the game in pygame
        if self.show:
            # Create a pygame screen
            self.cell_size = eval(config.get('WindowGame', 'cell_size'))
            screen_size = (self.cell_size * (self.board_size[1] * 2), 
                           self.cell_size * (self.board_size[0]))
            self.pygame_win = pygame.display.set_mode(screen_size)
            # Set the fps
            self.clock = pygame.time.Clock() 
            self.fps_play = eval(config.get('WindowGame', 'fps_play'))
            self.fps_train = eval(config.get('WindowGame', 'fps_train'))
            # Set the game bbox
            x0, y0 = (self.board_size[1] * self.cell_size, 0)
            width, height = (self.board_size[1] * self.cell_size, self.board_size[0] * self.cell_size)
            bbox_game = (x0, y0, width, height)
            # Set the network bbox
            x0, y0 = (0, 0)
            width, height = (self.board_size[1] * self.cell_size, self.board_size[0] * self.cell_size)
            bbox_network = (x0, y0, width, height)
            
            self.window_game = WindowGame(self.game, self.pygame_win, 
                                          cell_size = self.cell_size, 
                                          bbox_game = bbox_game,
                                          bbox_network = bbox_network)
            self.show_grid = eval(config.get('WindowGame', 'show_grid'))
            self.show_vision = eval(config.get('WindowGame', 'show_vision'))
        
        # In Game Status
        # ------
        self._pause = True
        self._run = False
        
        # Snakes Inner Params
        # -------------------
        self.snake_params = {
            "length": eval(config.get('Snake', 'length')),
            "vision_type": str(config.get('Snake', 'vision_type')),
            "vision_mode": eval(config.get('Snake', 'vision_mode')),
            "max_lifespan": eval(config.get('Snake', 'max_lifespan')),
            # Neural Network
            "nn_hidden_layers": eval(config.get('NeuralNetwork', 'hidden_layers')),
            # self.activation_hidden = eval(config.get('NeuralNetwork', 'activation_hidden')),
            # self.activation_output = eval(config.get('NeuralNetwork', 'activation_output'))
            }
                            
        # Genetic Algorithm
        # -----------------
        self.num_generations = eval(config.get('GeneticAlgorithm', 'num_generations'))
        self.num_parents = eval(config.get('GeneticAlgorithm', 'num_parents'))
        self.num_offspring = eval(config.get('GeneticAlgorithm', 'num_offspring'))
        self.num_population = self.num_parents + self.num_offspring
        self.eta_SBX = eval(config.get('GeneticAlgorithm', 'eta_SBX'))
        self.probability_SBX = eval(config.get('GeneticAlgorithm', 'probability_SBX'))
        self.probability_SPBX = eval(config.get('GeneticAlgorithm', 'probability_SPBX'))
        self.crossover_selection_type = str(config.get('GeneticAlgorithm', 'crossover_selection_type'))
        self.mutation_rate = eval(config.get('GeneticAlgorithm', 'mutation_rate'))
        self.mutation_rate_type = str(config.get('GeneticAlgorithm', 'mutation_rate_type'))
        self.gaussian_mu = eval(config.get('GeneticAlgorithm', 'gaussian_mu'))
        self.gaussian_std = eval(config.get('GeneticAlgorithm', 'gaussian_std'))
        

    def _player_controler(self, snake):
        # Quit
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._run = False
                pygame.quit()
                quit()
        # Update the direction
        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]:
            snake.direction = Direction.UP
            self._pause = False
        elif keys[pygame.K_RIGHT]:
            snake.direction = Direction.RIGHT
            self._pause = False
        elif keys[pygame.K_DOWN]:
            snake.direction = Direction.DOWN
            self._pause = False
        elif keys[pygame.K_LEFT]:
            snake.direction = Direction.LEFT
            self._pause = False
        # Pause the game
        elif keys[pygame.K_SPACE]:
            self._pause = not self._pause
        # Show the vision
        elif keys[pygame.K_v]:
            self.show_vision = not self.show_vision
        # Show the grid
        elif keys[pygame.K_g]:
            self.show_grid = not self.show_grid
        

    def play(self, snake=None):
               
        # Make sure you can play the game
        if snake is None:
            snake = Snake(self.game, **self.snake_params)       
        self.game.start(snake)
            
        # Run the game until the end
        self._run = True
        while self._run:
            
            # Render the game
            if self.show:
                self.window_game.draw(show_grid=self.show_grid, show_vision=self.show_vision)
                self.clock.tick(self.fps_play)
                # Player controler
                self._player_controler(snake)
                                    
            # Always move the snake if not paused
            if not self._pause:
                is_alive = snake.move()
                
                if not is_alive:
                    snake = Snake(self.game, **self.snake_params)
                    self.game.start(snake)
                    self._pause = True
                    
    
    def train(self):
        fitness = []  # For tracking average fitness over generation
        
        # Create and initialize the population
        individuals = [Snake(Game(self.board_size), **self.snake_params) for i in range(self.num_population)]                
        population = Population(individuals)
               
        for generation in range(self.num_generations):
            next_individuals = []  # For setting next population
            
            # Play all snakes in their games environment
            for i in range(self.num_population):
                chromosomes = population.individuals[i].chromosomes
                snake = Snake(self.game, chromosomes=chromosomes, **self.snake_params)
                self.game.start(snake)
                
                # Run the game until the end
                is_alive = True
                self._pause = False
                while is_alive:
                    
                    # Render the game
                    if self.show:
                        self._player_controler(snake)
                        self.window_game.draw(show_grid=self.show_grid, show_vision=self.show_vision)
                        
                        # Ellapsed time between two frames
                        self.clock.tick(self.fps_train)   

                    if not self._pause:
                        next_direction = snake.next_direction()
                        snake.direction = next_direction
                        is_alive = snake.move()
                        
                        if not is_alive:
                            # Update the population wit the final fitness
                            snake.calculate_fitness()
                            population.individuals[i] = snake  
                            self.game.clean()
            
            print("----------------------")
            print("Generation :{0:4d}/{1}".format(generation + 1, self.num_generations), end = " | ")
            print("best fitness : {0:2.3E}".format(population.fittest.fitness), end = " | ")
            print("best score : {0:2d}".format(population.fittest.score), end = " | ")
            print("lifespan : {0:3d}".format( population.fittest.lifespan), end = " | ")
            
            # Get best individuals from current pop
            best_from_pop = population.select_elitism(self.num_parents)
            next_individuals.extend(best_from_pop)
            
            while len(next_individuals) < self.num_population:
                parent1, parent2 = population.select_roulette_wheel(2)
                # parent1, parent2 = pop.select_tournament(2, 100)
            
                # Create offpsring through crossover
                if rd.random() > self.probability_SBX:
                    chromosomes_child1, chromosomes_child2 = population.crossover_simulated_binary(parent1, parent2, eta=100)
                else:
                    chromosomes_child1, chromosomes_child2 = population.crossover_single_point(parent1, parent2)
                    
                snake_child1 = Snake(Game(self.board_size), chromosomes=chromosomes_child1, **self.snake_params)
                snake_child2 = Snake(Game(self.board_size), chromosomes=chromosomes_child2, **self.snake_params)    
                mutation_rate = self.mutation_rate
                snake_child1.mutate(mutation_rate)
                snake_child2.mutate(mutation_rate)
                
                next_individuals.extend([snake_child1, snake_child2])
                                   
            # Track average fitness
            fitness.append(population.mean_fitness)
    
            # Set the next generation
            population.individuals = next_individuals
            
        print("\n\nBest individual :\n")
        print(population.fittest)
                        
        return population, fitness
    
    
    
    







        
        