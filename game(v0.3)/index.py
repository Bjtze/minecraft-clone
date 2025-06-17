from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from datetime import datetime
import keyboard, sys, time, json, os, random

app = Ursina()

def log(message):
    with open('debug.log', 'a') as log_file:
        log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


log('Game started')

terrain_size = 40

grass_texture = load_texture('assets/grass_block.png')
stone_texture = load_texture('assets/stone_block.png')
wood_texture = load_texture('assets/wooden_planks.png')
cobble_texture = load_texture('assets/cobblestone.png')
dirt_texture = load_texture('assets/dirt.jpg')
leaves_texture = load_texture('assets/leaves.jpg')
log_texture = load_texture('assets/log.png')
dev_block_texture = load_texture('assets/dev_block.jpg')

spawner_texture = load_texture('assets/spawner.jpg')
mob_texture = load_texture('assets/entity.png')
mob2_texture = load_texture('assets/josh.jpg')
arm_texture = load_texture('assets/arm_texture.png')

music = Audio('assets/music.mp3', loop=True, autoplay=True)

textures = [grass_texture, stone_texture, wood_texture, cobble_texture, dirt_texture, leaves_texture, log_texture, spawner_texture, dev_block_texture]
texture_names = ['Grass', 'Stone', 'Wood', 'Cobble', 'Dirt', 'Leaves', 'Log', 'Spawner', 'Dev']
selected_index = 0
selected_block_texture = textures[selected_index]

sky_texture = load_texture('assets/skybox.jpg')
sky = Sky()
sky.texture = sky_texture

hand = Entity(
    parent=camera.ui,
    model='assets/sword.obj',
    texture=arm_texture,
    scale=0.2,
    position=Vec2(0.6, -0.6),
    enabled=False
)

preview_icon = Entity(parent=camera.ui, model='quad', texture=selected_block_texture, scale=0.1, position=Vec2(0, -0.45), enabled=False)

menu_background = Entity(parent=camera.ui, model='quad', color=color.black66, scale=2)
menu_title = Text('Voxel Game', scale=3, position=Vec2(0, 0.3), origin=(0, 0), background=True)
start_button = Button(text='Start Game', scale=(0.3, 0.1), position=Vec2(0, 0), color=color.azure)
load_button = Button(text='Load World', scale=(0.3, 0.1), position=Vec2(0, -0.15), color=color.orange)
save_button = Button(text='Save World', scale=(0.3, 0.1), position=Vec2(0, -0.3), color=color.green)
quit_button = Button(text='Quit', scale=(0.3, 0.1), position=Vec2(0, -0.45), color=color.red)

game_running = False
blocks = []
mobs = []
spawners = []
projectiles = []
SAVE_FILE = 'world_save.json'

projectiles_destroyed = 0
last_reset_time = time.time()

health_bar_bg = Entity(parent=camera.ui, model='quad', color=color.dark_gray, scale=(1, 0.05), position=Vec2(0, 0.45))
health_bar = Entity(parent=camera.ui, model='quad', color=color.red, scale=(0.5, 0.05), position=Vec2(0, 0.45), origin_x=-0)
displayed_health = 100 

regen_rate = 1  # HP per interval
regen_interval = 0.5  # seconds
last_regen_time = time.time()

class Block(Button):
    def __init__(self, position=(0,0,0), texture=grass_texture):
        super().__init__(parent=scene, position=position, model='cube', origin_y=0.5,
                         texture=texture, color=color.color(0, 0, random.uniform(0.9, 1.0)), scale=1)
        self.is_block = True


class Mob(Entity):
    def __init__(self, position=(5, 1, 5), max_health=100, attack_damage=2, attack_cooldown=2, speed=1, lifespan=300):
        super().__init__(
            model='cube',
            texture=mob_texture,
            scale=(4, 0.5, 4),
            position=position,
            collider='box'
        )
        self.velocity_y = 0
        self.gravity = 9.8
        self.on_ground = False
        self.speed = speed
        self.direction = Vec3(random.choice([-1, 1]), 0, random.choice([-1, 1]))
        self.spawn_time = time.time()
        self.lifespan = lifespan
        self.freeze_until = time.time() + random.uniform(1, 2)

        # Combat attributes
        self.max_health = max_health
        self.health = self.max_health
        self.attack_damage = attack_damage
        self.attack_cooldown = attack_cooldown
        self.last_attack_time = time.time()
        self.ranged_cooldown = 0.2
        self.last_ranged_time = time.time()

        # AI
        self.chase_radius = 20
        self.attack_radius = 2

    def update(self):
        if time.time() < self.freeze_until:
            return

        # Gravity
        ray = raycast(
            self.world_position + Vec3(0, 0.5, 0),
            direction=Vec3(0, -1, 0),
            distance=1,
            ignore=(self,)
        )
        self.on_ground = ray.hit

        if self.on_ground:
            self.velocity_y = 0
        else:
            self.velocity_y -= self.gravity * time.dt
            self.y += self.velocity_y * time.dt

        # Distance to player
        to_player = player.position - self.position
        dist = to_player.length()

        # Ranged attack (if mid-range)
        if 3 < dist < self.chase_radius:
            if time.time() - self.last_ranged_time >= self.ranged_cooldown:
                direction = to_player
                projectile = Projectile(
                    position=self.position + Vec3(0, 1, 0),
                    direction=direction,
                    damage=self.attack_damage
                )
                projectiles.append(projectile)
                self.last_ranged_time = time.time()

        # Movement & chasing
        if dist < self.chase_radius:
            self.direction = to_player.normalized()
        else:
            if random.random() < 0.01:
                self.direction = Vec3(
                    random.choice([-1, 0, 1]), 0, random.choice([-1, 0, 1])
                )

        movement = self.direction * self.speed * time.dt
        next_pos = self.position + movement

        temp = Entity(model='cube', scale=self.scale, position=next_pos, collider='box')
        hit = temp.intersects()
        destroy(temp)

        if hit.hit and hasattr(hit.entity, 'is_block'):
            self.direction = Vec3(
                random.choice([-1, 0, 1]), 0, random.choice([-1, 0, 1])
            )
        else:
            self.position = next_pos

        if dist < self.attack_radius:
            if time.time() - self.last_attack_time >= self.attack_cooldown:
                player.health -= self.attack_damage
                self.last_attack_time = time.time()
                log(f"{self.__class__.__name__} attacked! Player HP: {player.health}")

        # Lifespan check
        if time.time() - self.spawn_time > self.lifespan:
            self.die()

    def take_damage(self, amount):
        self.health -= amount
        log(f"{self.__class__.__name__} took {amount} damage. HP: {self.health}")
        self.damage_animation() 
        if self.health <= 0:
            self.die()

    def die(self):
        self.animate_scale(Vec3(0, 0, 0), duration=0.5)
        self.fade_out(duration=0.5)
        invoke(self.cleanup, delay=0.5)

    def cleanup(self):
        if self in mobs:
            mobs.remove(self)
        destroy(self)

    def damage_animation(self):
        original_color = self.color
        self.color = color.red
        self.animate_color(original_color, duration=0.2)
        self.animate_scale(self.scale * Vec3(1.1, 0.9, 1.1), duration=0.1)
        invoke(lambda: setattr(self, 'scale', Vec3(4, 0.5, 4)), delay=0.1)


class Projectile(Entity):
    def __init__(self, position, direction, speed=5, damage=5, lifetime=3):
        super().__init__(
            model='sphere',
            color=color.orange,
            scale=0.3,
            position=position,
            collider='sphere'
        )
        self.direction = direction.normalized()
        self.speed = speed
        self.damage = damage
        self.spawn_time = time.time()
        self.lifetime = lifetime

    def update(self):
        if not self.enabled:
            return

        self.position += self.direction * self.speed * time.dt

        # Hit detection
        if distance(self.position, player.position) < 1.5:
            player.health -= self.damage
            log(f"Hit by projectile! Player HP: {player.health}")
            self.enabled = False
            invoke(destroy, self, delay=0.01)
            return

        # Lifetime expiration
        if time.time() - self.spawn_time > self.lifetime:
            self.enabled = False
            invoke(destroy, self, delay=0.01)

class Mob2(Mob):
    def __init__(self, position=(5, 1, 5)):
        super().__init__(position)
        self.texture = mob2_texture
        self.scale = (1, 2, 1)
        self.attack_cooldown = 2
        self.last_attack_time = time.time()
        self.max_health = 30
        self.health = self.max_health
        self.health_bar = Entity(
            parent=self,
            model='quad',
            color=color.red,
            scale=(0.5, 0.05),
            position=Vec3(0, 1.2, 0),
            origin_x=-0.5
        )

    def update(self):
        global music

        if time.time() < self.freeze_until:
            return

            # Gravity logic
        ray = raycast(
            self.world_position + Vec3(0, 0.5, 0),
            direction=Vec3(0, -1, 0),
            distance=1,
            ignore=(self,)
        )
        self.on_ground = ray.hit

        if self.on_ground:
            self.velocity_y = 0
        else:
            self.velocity_y -= self.gravity * time.dt
            self.y += self.velocity_y * time.dt

            # Distance to player
        to_player = player.position - self.position
        dist = to_player.length()

            # Movement/chasing
        if dist < self.chase_radius:
            self.direction = to_player.normalized()
        else:
            if random.random() < 0.01:
                self.direction = Vec3(random.choice([-1, 0, 1]), 0, random.choice([-1, 0, 1]))

        movement = self.direction * self.speed * time.dt
        next_pos = self.position + movement

        temp = Entity(model='cube', scale=self.scale, position=next_pos, collider='box')
        hit = temp.intersects()
        destroy(temp)

        if hit.hit and hasattr(hit.entity, 'is_block'):
            self.direction = Vec3(random.choice([-1, 0, 1]), 0, random.choice([-1, 0, 1]))
        else:
            self.position = next_pos

            # Melee attack
        if dist < self.attack_radius:
            if time.time() - self.last_attack_time >= self.attack_cooldown:
                player.health -= self.attack_damage
                self.last_attack_time = time.time()
                log(f"{self.__class__.__name__} attacked! Player HP: {player.health}")

            # Health bar update
        if hasattr(self, 'health_bar'):
            ratio = max(self.health / self.max_health, 0)
            self.health_bar.scale_x = 0.5 * ratio

            # Lifetime
        if time.time() - self.spawn_time > self.lifespan:
            self.die()

        def die(self):
            self.animate_scale(Vec3(0, 0, 0), duration=0.5)
            self.fade_out(duration=0.5)
            invoke(self.cleanup, delay=0.5)

        def cleanup(self):
            if self in mobs:
                mobs.remove(self)
            destroy(self)

        def take_damage(self, amount):
            self.health -= amount
            log(f"Mob2 took {amount} damage! Remaining HP: {self.health}")
            self.damage_animation()
            if self.health <= 0:
                self.die()
                
        def damage_animation(self):
            original_color = self.color
            self.color = color.red
            self.animate_color(original_color, duration=0.2)
            self.animate_scale(self.scale * Vec3(1.1, 0.9, 1.1), duration=0.1)
            invoke(lambda: setattr(self, 'scale', Vec3(1, 2, 1)), delay=0.1)



class Mob2Spawner(Entity):
    def __init__(self, position=(0,1,0), spawn_interval=5):
        super().__init__(model='cube', texture=spawner_texture, scale=1, position=position, collider='box')
        self.spawn_interval = spawn_interval
        self.last_spawn_time = time.time()
        self.hit_points = 5

    def update(self):
        if time.time() - self.last_spawn_time >= self.spawn_interval:
            for _ in range(3):
                mob = Mob2(position=self.position + Vec3(1,0,1))
                mobs.append(mob)
            self.last_spawn_time = time.time()

class Weapon:
    def __init__(self, name, damage, cooldown, model=None, texture=None):
        self.name = name
        self.damage = damage
        self.cooldown = cooldown
        self.model = model
        self.texture = texture
        self.last_attack_time = 0

    def can_attack(self):
        return time.time() - self.last_attack_time >= self.cooldown

    def attack(self):
        self.last_attack_time = time.time()

def update():
    global selected_block_texture, selected_index, game_running, projectiles, music, projectiles_destroyed, last_reset_time

        # Remove excess projectiles
    while len(projectiles) > 110:
        destroy(projectiles.pop(0))
        projectiles_destroyed += 1

    # Reset the counter every 5 seconds and print the result
    if time.time() - last_reset_time >= 5:
        log(f"Popped {projectiles_destroyed} projectiles in the last 5 seconds.")
        projectiles_destroyed = 0
        last_reset_time = time.time()


    if keyboard.is_pressed('escape') and game_running:
        pause_game()

    if not game_running:
        return
    

    hand.rotation_z = -10 if held_keys['left mouse'] or held_keys['right mouse'] else 0

    if held_keys['left mouse']:
        hit_info = mouse.hovered_entity
        if hit_info:
            if isinstance(hit_info, (Mob, Mob2)):
                if player.weapon.can_attack():
                    player.weapon.attack()
                    hit_info.take_damage(player.weapon.damage)

            elif isinstance(hit_info, Mob2Spawner):
                hit_info.hit_points -= 1
                log(f"Spawner hit! Remaining: {hit_info.hit_points}")
                if hit_info.hit_points <= 0:
                    if hit_info in spawners:
                        spawners.remove(hit_info)
                    destroy(hit_info)
                    log("Spawner destroyed!")
                time.sleep(0.2)

            elif hasattr(hit_info, 'is_block'):
                if hit_info.texture == dev_block_texture:
                    log("Unbreakable block cannot be destroyed.")
                else:
                    if hit_info in blocks:
                        blocks.remove(hit_info)
                    destroy(hit_info)
                    time.sleep(0.2)



    if held_keys['right mouse']:
        hit_info = mouse.hovered_entity
        if hit_info and hasattr(hit_info, 'is_block'):
            position = hit_info.position + mouse.normal
            if selected_block_texture == spawner_texture:
                spawner = Mob2Spawner(position=position)
                spawners.append(spawner)
            else:
                block = Block(position=position, texture=selected_block_texture)
                blocks.append(block)
            time.sleep(0.2)



    for i in range(9):
        if keyboard.is_pressed(str(i+1)):
            selected_index = i

    selected_block_texture = textures[selected_index]
    preview_icon.texture = selected_block_texture

    if keyboard.is_pressed('n'):
        for mob in mobs:
            destroy(mob)
        mobs.clear()

    for mob in mobs:
        mob.update()

    for p in projectiles:
        p.update()

    projectiles = [p for p in projectiles if p.enabled]


    for spawner in spawners:
        spawner.update()

    if keyboard.is_pressed('m'):
        mob = Mob(position=player.position + Vec3(2,0,2))
        log("Boss summoned")

    if keyboard.is_pressed('b'):
        mob = Mob2(position=player.position + Vec3(2,0,2))
        mobs.append(mob)
        log("Mob2 summoned (with B)")

    if keyboard.is_pressed('e'):
        weapon_menu_bg.enabled = not weapon_menu_bg.enabled

    if player.health > 100:
        health_bar.color = color.yellow
    else:
        health_bar.color = color.red

    global displayed_health
    displayed_health = lerp(displayed_health, player.health, 1 * time.dt)
    health_bar.scale_x = 0.5 * max(displayed_health / 100, 0)

    if player.health <= 0:
        log("You died!")
        pause_game()

    health_ratio = max(player.health / 100, 0)
    health_bar.scale_x = 1 * health_ratio

    # Health regeneration logic
    global last_regen_time
    if player.health < 100 and time.time() - last_regen_time > regen_interval:
        player.health = min(100, player.health + regen_rate)
        last_regen_time = time.time()

def save_world():
    data = []
    for block in blocks:
        data.append({'position': tuple(block.position), 'texture': texture_names[textures.index(block.texture)]})
    with open(SAVE_FILE, 'w') as f:
        json.dump(data, f)
    log('World saved!')

def load_world():
    if not os.path.exists(SAVE_FILE):
        return
    for b in blocks: destroy(b)
    blocks.clear()
    with open(SAVE_FILE, 'r') as f:
        data = json.load(f)
    for entry in data:
        texture = textures[texture_names.index(entry['texture'])]
        block = Block(position=entry['position'], texture=texture)
        blocks.append(block)
    log('World loaded!')

for z in range(terrain_size):
    for x in range(terrain_size):
        block = Block(position=(x, 0, z))
        blocks.append(block)

player = FirstPersonController()
player.gravity = 0.5
player.jump_height = 5
player.enabled = False
player.health = 100


player.weapons = [
    Weapon("Basic Sword", damage=10, cooldown=0.5),
    Weapon("Axe", damage=15, cooldown=0.8),
    Weapon("DO NOT USE", damage=100, cooldown=2),
]
player.weapon_index = 0
player.weapon = player.weapons[player.weapon_index]

weapon_label = Text(
    text=f"Weapon: {player.weapon.name}",
    position=Vec2(-0.85, 0.4),
    scale=1.5,
    origin=(0, 0),
    background=True
)

weapon_menu_bg = Entity(parent=camera.ui, model='quad', color=color.black66, scale=(1, 0.5), position=Vec2(0, 0), enabled=False)
weapon_buttons = []

def create_weapon_buttons():
    for i, weapon in enumerate(player.weapons):
        btn = Button(
            text=weapon.name,
            parent=weapon_menu_bg,
            position=Vec2(-0.4 + i * 0.4, 0),
            scale=(0.3, 0.1),
            color=color.azure
        )
        def select_weapon(i=i):
            player.weapon_index = i
            player.weapon = player.weapons[i]
            weapon_label.text = f"Weapon: {player.weapon.name}"
            print(f"Switched to: {player.weapon.name}")
            weapon_menu_bg.enabled = False

        btn.on_click = select_weapon
        weapon_buttons.append(btn)

create_weapon_buttons()

def start_game():
    global game_running
    game_running = True
    player.enabled = True
    hand.enabled = True
    preview_icon.enabled = True
    menu_background.enabled = False
    menu_title.enabled = False
    start_button.enabled = False
    load_button.enabled = False
    save_button.enabled = False
    quit_button.enabled = False


def pause_game():
    global game_running
    game_running = False
    player.enabled = False
    hand.enabled = False
    preview_icon.enabled = False
    menu_background.enabled = True
    menu_title.enabled = True
    start_button.enabled = True
    load_button.enabled = True
    save_button.enabled = True
    quit_button.enabled = True

def quit_game():
    sys.exit()

start_button.on_click = start_game
load_button.on_click = load_world
save_button.on_click = save_world
quit_button.on_click = quit_game

app.run()
