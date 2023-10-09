import copy
import socketio
import numpy as np
from queue import PriorityQueue
from game_info import GameInfo
from collections import deque
from const import (
    NextMove,
    Spoil,
    ValidPos,
    InvalidPos,
    valid_pos_set,
    spoil_set,
)

sio = socketio.Client()


map_states = []
normal_queue = []
previous_timestamp = 0
directions = {
    NextMove.UP: (-1, 0),
    NextMove.LEFT: (0, -1),
    NextMove.RIGHT: (0, 1),
    NextMove.DOWN: (1, 0)
}


class GameBot:
    def __init__(
            self,
            player_id,
            cur_pos,
            lives,
            speed,
            power,
            delay
    ):
        self._id = player_id
        self._pos = cur_pos
        self._lives = lives
        self._speed = speed
        self._power = power
        self._delay = delay

    @property
    def id(self):
        return self._id

    @property
    def pos(self):
        return self._pos

    @property
    def lives(self):
        return self._lives

    @property
    def speed(self):
        return self._speed

    @property
    def power(self):
        return self._power

    @property
    def delay(self):
        return self._delay


class GameMap:

    def __init__(self, data):
        self._tag = data['tag']
        self._id = data['id']
        self._timestamp = data['timestamp']
        self._map_info = data["map_info"]
        self._my_bot = None
        self._opp_bot = None
        self._max_row = self.map_info['size']['rows']
        self._max_col = self.map_info['size']['cols']
        self.map_matrix = np.array(self.map_info['map'])  # convert 2d matrix into ndarray data type
        self.spoils = dict()
        self.targets = dict()
        self.bombs = dict()

    @property
    def tag(self):
        return self._tag

    @property
    def id(self):
        return self._id

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def map_info(self):
        return self._map_info

    @property
    def my_bot(self):
        return self._my_bot

    @my_bot.setter
    def my_bot(self, value):
        self._my_bot = value

    @property
    def opp_bot(self):
        return self._opp_bot

    @opp_bot.setter
    def opp_bot(self, value):
        self._opp_bot = value

    @property
    def max_row(self):
        return self._max_row

    @property
    def max_col(self):
        return self._max_col

    def find_bots(self):
        for player in self.map_info['players']:
            player_id = player.get('id')
            player_pos = (
                player.get('currentPosition')['row'],
                player.get('currentPosition')['col']
            )
            player_lives = player.get('lives')
            player_speed = player.get('speed')
            player_power = player.get('power')
            player_delay = player.get('delay')
            game_bot = GameBot(
                player_id,
                player_pos,
                player_lives,
                player_speed,
                player_power,
                player_delay
            )
            if player_id == GameInfo.PLAYER_ID:
                self.my_bot = game_bot
            else:
                self.opp_bot = game_bot

    def near_balk(self, pos):
        """Return True if pos near the balk."""
        for direction in directions.values():
            row = pos[0] + direction[0]
            col = pos[1] + direction[1]
            if row < 0 or row >= self.max_row or col < 0 or col >= self.max_col:
                continue
            if self.map_matrix[pos[0] + direction[0]][pos[1] + direction[1]] == ValidPos.BALK.value:
                return True
        return False

    def _fill_spoils(self, map_spoils):
        """Fill all spoils into the map matrix."""
        for spoil in map_spoils:
            row = spoil['row']
            col = spoil['col']
            spoil_type = spoil['spoil_type'] + Spoil.BIAS.value

            # 6: Speed, 7: Power, 8: Delay, 9: Mystic
            self.map_matrix[row][col] = spoil_type
            self.spoils[(row, col)] = spoil_type

    def _fill_bombs(self, map_bombs):
        """Fill all bombs into the map matrix."""
        bomb_power = 1
        for bomb in map_bombs:
            bomb_pos = (bomb['row'], bomb['col'])
            remain_time = bomb['remainTime']
            # 13: Bomb
            self.map_matrix[bomb_pos[0]][bomb_pos[1]] = InvalidPos.BOMB.value
            self.bombs[bomb_pos] = {
                'power': bomb_power,
                'remain_time': remain_time
            }

    def fill_map(self):
        """Fill all map matrix"""
        self._fill_spoils(self.map_info['spoils'])
        self._fill_bombs(self.map_info['bombs'])

    def avail_moves(self, cur_pos):
        """All available moves with current position."""
        res = []
        for route, direction in directions.items():
            next_move = (cur_pos[0] + direction[0], cur_pos[1] + direction[1])
            if next_move[0] < 0 or next_move[0] >= self.max_row or next_move[1] < 0 or next_move[1] >= self.max_col:
                continue
            if next_move == self.opp_bot.pos:
                continue

            if self.map_matrix[next_move[0]][next_move[1]] in valid_pos_set:
                res.append((route.value, next_move))
        return res

    def place_bombs(self, cur_pos):
        """Return next_move is 'b' if my bot can place a bomb."""
        avail_moves = self.avail_moves(cur_pos)
        if len(avail_moves) == 0:
            return [], []

        if self.near_balk(cur_pos):
            moves, next_poses = deque(avail_moves[0][0]), deque(avail_moves[0][1])
            if len(moves) > 0:
                moves.appendleft('b')
                return moves, next_poses
        return [], []

    @staticmethod
    def all_moves(cur_pos):
        res = []
        for action, direction in directions.values():
            next_move = (cur_pos[0] + direction[0], cur_pos[1] + direction[1])
            res.append((action, next_move))
        return res


def greedy_bfs(game_map):
    min_row = max(game_map.my_bot.pos[0] - 7, 0)
    max_row = min(game_map.my_bot.pos[0] + 7, game_map.max_row - 1)
    min_col = max(game_map.my_bot.pos[1] - 7, 0)
    max_col = min(game_map.my_bot.pos[1] + 7, game_map.max_col - 1)

    all_routes = PriorityQueue()
    saved = set()
    my_pos = game_map.my_bot.pos
    saved.add(my_pos)
    move_queue = deque()
    move_queue.append([my_pos, [], [], 0])

    while len(move_queue) > 0:
        pos, routes, poses, score = move_queue.popleft()
        moves, next_poses = game_map.place_bombs(pos)
        if len(moves) > 0:
            r = copy.deepcopy(routes)
            r.extend(moves)
            p = copy.deepcopy(poses)
            p.extend(next_poses)
            all_routes.put((-1, (-1, r, p, 13)))
            break

        if game_map.map_matrix[pos[0]][pos[1]] in spoil_set:
            all_routes.put((0, (0, routes, poses, game_map.map_matrix[pos[0]][pos[1]])))
            break

        next_routes = []  # Save all routes along with related information.
        for route, direction in directions.items():
            next_pos = (pos[0] + direction[0], pos[1] + direction[1])

            if next_pos in saved:
                continue
            # invalid positions
            if next_pos[0] < min_row or next_pos[0] > max_row or next_pos[1] < min_col or next_pos[1] > max_col:
                continue
            # valid positions
            if game_map.map_matrix[next_pos[0]][next_pos[1]] in valid_pos_set:
                saved.add(next_pos)
                next_routes.append([next_pos, score + 1, route.value])

        for move in next_routes:
            r = copy.deepcopy(routes)
            r.append(move[2])
            p = copy.deepcopy(poses)
            p.append(move[0])
            move_queue.append([move[0], r, p, move[1]])

    if not all_routes.empty():
        return all_routes.get()

    return None


@sio.event
def send_infor():
    infor = {"game_id": GameInfo.GAME_ID, "player_id": GameInfo.PLAYER_ID}
    sio.emit('join game', infor)


@sio.on('join game')
def join_game(data):
    print('joined game!!!!')


# @sio.on('drive player')
# def receive_moves(data):
#     print(f'Received: {data}')


@sio.event
def next_moves(moves):
    sio.emit('drive player', {"direction": moves})


@sio.event
def connect():
    print('connection established')
    send_infor()


@sio.on('ticktack player')
def map_state(data):
    global normal_queue
    global previous_timestamp

    map_states.append(data)
    cur_map = map_states.pop()
    game_map = GameMap(cur_map)
    game_map.find_bots()

    if len(normal_queue) > 0:
        next_move = normal_queue.pop()
        next_moves(next_move[1][0])
        previous_timestamp = game_map.timestamp

    if game_map.timestamp - previous_timestamp > 300:
        drive_bot(game_map)


def drive_bot(game_map):
    game_map.fill_map()
    map_id = game_map.id
    game_tag = game_map.tag
    my_pos = game_map.my_bot.pos

    print(f'DEBUG - {map_id} - {game_tag}: My pos: {my_pos}')
    normal_routes = greedy_bfs(game_map)
    if normal_routes:
        priority_route = normal_routes[1]
        my_route = priority_route[1]
        normal_queue.append(
            (game_map.id, (''.join(my_route), game_map.my_bot.pos, priority_route[2], priority_route[3])))

    else:
        avail_moves = game_map.avail_moves(my_pos)
        if len(avail_moves) > 0:
            my_route = [avail_moves[0][0]]
            normal_queue.append(
                (game_map.id, (''.join(my_route), game_map.my_bot.pos, [avail_moves[0][1]], 0)))


def main():
    sio.connect('http://localhost:80', transports=['websocket'])
    sio.wait()


if __name__ == '__main__':
    main()
