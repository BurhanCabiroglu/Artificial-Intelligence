import collections
import datetime
import gym
import gym_tictactoe
import matplotlib.pyplot as plt
import numpy as np
import os
import random
import seaborn as sns
import sys
import tensorflow as tf
from tensorflow import keras
import time
import traceback


tf.compat.v1.disable_eager_execution()


class RLAgent:

    def __init__(self, env, maximizer=True, load_weights=None):
        self.epsilon = 1.0
        self.epsilon_decay = 0.9975
        self.epsilon_min = 0.001
        self.gamma = 0.99
        self.learning_rate = 0.0001
        self.learning_rate_decay = 0.01
        self.max_tau = 1000
        self.tau = 0

        self.batch_size = 64

        self.replay_buffer = collections.deque(maxlen=10000)
        self.state_size = [env.observation_space.n]
        self.action_size = env.action_space['pos'].n
        self.maximizer = maximizer
        if load_weights is not None:
            self.model = self.loadModel(load_weights)
        else:
            self.model = self.build_model()
        self.updateTargetNetwork()
        print("\nINFO")
        print("-------------------")
        print("State Size  : {}".format(self.state_size))
        print("Action Size : {}".format(self.action_size))
        print("-------------------")

    # Update the target network
    def updateTargetNetwork(self):
        print("Updating Target Network")
        self.target_model = keras.models.clone_model(self.model)
        self.target_model.set_weights(self.model.get_weights())
        self.tau = 0

    # Define the layers of the neural network model
    def build_model(self):
        model = keras.models.Sequential()
        model.add(keras.layers.Dense(32, activation="relu", input_shape=self.state_size))
        model.add(keras.layers.Dense(self.action_size))
        model.compile(
            optimizer=keras.optimizers.Adam(lr=self.learning_rate),
            loss='mse')
        model.summary()
        return model

    # Save the model
    def saveModel(self):
        global PARENT_DIR, RUN_ID
        self.model.save(os.path.join(PARENT_DIR, 'data\\saved_models', 'model_{}.h5'.format(RUN_ID)))

    # Save the model
    def loadModel(self, file_name):
        global PARENT_DIR, GAME
        weights_file = os.path.join(PARENT_DIR, 'data\\saved_models', file_name)
        if os.path.isfile(weights_file):
            print("Loaded model from disk")
            self.epsilon = self.epsilon_min
            return keras.models.load_model(weights_file)
        else:
            print("Could not find file. Initializing the model")
            return self.build_model()

    # Get best action from policy
    def getAction(self, state):
        state = np.reshape(state, (1, self.state_size[0]))
        if np.random.rand() <= self.epsilon:
            # Exploration
            return np.random.randint(self.action_size)
        else:
            # Exploitation
            output = self.model.predict(state)
            return np.argmax(output)

    # Save an experience for training during a later time
    def saveExperience(self, state, action, reward, next_state, done):
        state = np.reshape(state, (1, self.state_size[0]))
        next_state = np.reshape(next_state, (1, self.state_size[0]))
        self.replay_buffer.append((state, action, reward, next_state, done))

    # Train the model parameters
    def trainModel(self):

        self.tau += 1
        if self.tau > self.max_tau:
            self.updateTargetNetwork()

        sample_size = min(self.batch_size, len(self.replay_buffer))
        minibatch = random.sample(self.replay_buffer, sample_size)
        batch_train_x = []
        batch_train_y = []

        for state, action, reward, next_state, done in minibatch:
            next_state_value = 0
            if not done:
                next_state_value = np.max(self.target_model.predict(next_state))

            action_value = reward + self.gamma * next_state_value
            target_values = self.model.predict(state)
            target_values[0][action] = action_value

            batch_train_x.append(state[0])
            batch_train_y.append(target_values[0])

        history = self.model.fit(
            np.array(batch_train_x),
            np.array(batch_train_y),
            batch_size=len(batch_train_x),
            epochs=1,
            verbose=False)
        agent.epsilon = max(agent.epsilon_min, agent.epsilon * agent.epsilon_decay)

        return history.history['loss'][0]


# Initialize the program and create necessary folders
def init(PARENT_DIR, GAME, SAVED_MODEL=None):

    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

    # Create the necessary folders
    recordings_folder = os.path.join(PARENT_DIR, 'data', 'recordings')
    if not os.path.exists(recordings_folder):
        os.makedirs(recordings_folder)

    tensorboard_folder = os.path.join(PARENT_DIR, 'data', 'tensorboard')
    if not os.path.exists(tensorboard_folder):
        os.makedirs(tensorboard_folder)

    modles_folder = os.path.join(PARENT_DIR, 'data', 'saved_models')
    if not os.path.exists(modles_folder):
        os.makedirs(modles_folder)

    # Initialize environment, agent and logger
    env = gym.make(GAME)
    # env = gym.wrappers.Monitor(env, os.path.join(PARENT_DIR, 'data/recordings/', RUN_ID), force=True)
    agent = RLAgent(env, maximizer=True, load_weights=SAVED_MODEL)
    summary_writer = tf.summary.create_file_writer(os.path.join(PARENT_DIR, 'data', 'tensorboard', RUN_ID))

    return (env, agent, summary_writer)


# Plot the metrics to Tensorboard for easier visualization
def plotMetrics(summary_writer, episode, epsilon, train_loss, max_step, total_reward, average_reward):

    with summary_writer.as_default():
        tf.summary.scalar('Epsilon', epsilon, step=episode)
        tf.summary.scalar('Loss', train_loss, step=episode)
        tf.summary.scalar('Steps', max_step, step=episode)
        tf.summary.scalar('Reward P0', total_reward[0], step=episode)
        tf.summary.scalar('Reward P1', -total_reward[1], step=episode)
        tf.summary.scalar('Reward Average (100) P0', np.mean(average_reward[0]), step=episode)
        tf.summary.scalar('Reward Average (100) P1', -np.mean(average_reward[1]), step=episode)

        summary_writer.flush()


def randomValidAction(state):

    valid_moves = []
    for i in range(9):
        if state[i] == 0 and state[i + 9] == 0:
            valid_moves.append(i)

    return random.choice(valid_moves)


# ~~~ MAIN CODE ~~~

# Global Variables and Constants

GAME = 'tictactoe-v0'
MAX_EPISODES = 20
MAX_STEPS = 100
RENDER = False
SAVED_MODEL = None
# SAVED_MODEL = 'model_2020-05-14 23-28-16.h5'

RUN_ID = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
PARENT_DIR = os.path.dirname(os.path.abspath(__file__))

env, agent, summary_writer = init(PARENT_DIR, GAME, SAVED_MODEL)
clock = time.time()
try:
    # Start the Simulation
    average_reward = [collections.deque(maxlen=100), collections.deque(maxlen=100)]
    for episode in range(MAX_EPISODES):
        total_loss = 0
        max_step = 0
        total_reward = [0, 0]

        state = env.reset()
        if RENDER:
            env.render()
        for step in range(MAX_STEPS):

            action = None
            if env.player_turn == 0:
                action = agent.getAction(state)
                action_formated = {'player': env.player_turn, 'pos': action}
                next_state, reward, done, info = env.step(action_formated)
                agent.saveExperience(state, action, reward[env.player_turn], next_state, done)

                state = next_state
                total_reward[0] += reward[0]
                total_reward[1] += reward[1]

                train_loss = agent.trainModel()
                total_loss += train_loss

            else:
                action = randomValidAction(state)
                action_formated = {'player': env.player_turn, 'pos': action}
                next_state, reward, done, info = env.step(action_formated)

                state = next_state
                total_reward[0] += reward[0]
                total_reward[1] += reward[1]

            if RENDER:
                env.render()
                time.sleep(1)

            if done:
                max_step = step
                average_reward[0].append(total_reward[0])
                average_reward[1].append(total_reward[1])
                print("Episode: {:4d} | Total Reward P0: {:+9.3f} | Total Reward P1: {:+9.3f} Frames : {:3d} |"
                      .format(episode, total_reward[0], -total_reward[1], max_step))
                break

        if not RENDER:
            plotMetrics(summary_writer, episode, agent.epsilon, total_loss, max_step, total_reward, average_reward)

    env.close()
except Exception as e:
    print(str(e))
    traceback.print_exc()
finally:
    print("Done. Time Taken : {:.2f}".format(time.time()-clock))
    agent.saveModel()
    env.close()
