import math, random, pygame
from . import config as C
from .models import Empire, StarSystem, Fleet
class World:
    def __init__(self, seed=None):
        self.rng=random.Random(seed); self.systems=[]; self.empires=[]; self.fleets=[]; self.edges=set(); self.neighbors={}; self.ai_timer=0; self.generate()
    def generate(self):
        self.systems=[]; self.empires=[]; self.fleets=[]; self.edges=set(); self.neighbors={}; self.ai_timer=0
        pos=[]
        for _ in range(12000):
            if len(pos)>=C.STAR_COUNT: break
            p=pygame.Vector2(self.rng.randint(70,C.WIDTH-70),self.rng.randint(95,C.HEIGHT-70))
            if all(p.distance_to(q)>=C.MIN_STAR_DISTANCE for q in pos): pos.append(p)
        while len(pos)<C.STAR_COUNT: pos.append(pygame.Vector2(self.rng.randint(70,C.WIDTH-70),self.rng.randint(95,C.HEIGHT-70)))
        for i,p in enumerate(pos):
            self.systems.append(StarSystem(i,f'System {i+1}',p,self.rng.uniform(C.PRODUCTION_MIN,C.PRODUCTION_MAX),float(self.rng.randint(2,13))))
            self.neighbors[i]=set()
        for s in self.systems:
            near=sorted((s.pos.distance_to(o.pos),o.id) for o in self.systems if o.id!=s.id)
            for _,j in near[:C.MIN_CONNECTIONS]: self.connect(s.id,j)
        for a in self.systems:
            for b in self.systems[a.id+1:]:
                d=a.pos.distance_to(b.pos)
                if d<=C.EDGE_DISTANCE and self.rng.random() < .56*(1-d/C.EDGE_DISTANCE)+.10: self.connect(a.id,b.id)
        while len(self.components())>1:
            comps=self.components(); best=min((self.systems[a].pos.distance_to(self.systems[b].pos),a,b) for a in comps[0] for comp in comps[1:] for b in comp); self.connect(best[1],best[2])
        for i in range(C.EMPIRE_COUNT): self.empires.append(Empire(i,f'Empire {i+1}',C.COLORS[i%len(C.COLORS)]))
        chosen=[self.rng.randrange(len(self.systems))]
        while len(chosen)<len(self.empires):
            chosen.append(max((i for i in range(len(self.systems)) if i not in chosen),key=lambda i:min(self.systems[i].pos.distance_to(self.systems[j].pos) for j in chosen)))
        for e,i in zip(self.empires,chosen): self.systems[i].owner_id=e.id; self.systems[i].ships=C.STARTING_SHIPS
    def connect(self,a,b):
        if a==b:return
        self.edges.add(tuple(sorted((a,b)))); self.neighbors[a].add(b); self.neighbors[b].add(a)
    def components(self):
        left=set(range(len(self.systems))); out=[]
        while left:
            stack=[next(iter(left))]; comp=set()
            while stack:
                n=stack.pop()
                if n in comp: continue
                comp.add(n); left.discard(n); stack.extend(self.neighbors[n]-comp)
            out.append(comp)
        return out
    def update(self,dt):
        for s in self.systems:
            if s.owner_id is not None:s.ships+=s.production*dt
        arrived=[]
        for f in self.fleets:
            a,b=self.systems[f.source_id],self.systems[f.target_id]; f.progress+=C.FLEET_SPEED*dt/max(1,a.pos.distance_to(b.pos))
            if f.progress>=1: arrived.append(f)
        for f in arrived:self.arrive(f);self.fleets.remove(f)
        self.ai_timer+=dt
        if self.ai_timer>=C.AI_INTERVAL:self.ai_timer-=C.AI_INTERVAL;self.run_ai()
        for e in self.empires:e.alive=any(s.owner_id==e.id for s in self.systems) or any(f.owner_id==e.id for f in self.fleets)
    def run_ai(self):
        for e in self.empires:
            if not e.alive:continue
            owned=[s for s in self.systems if s.owner_id==e.id];self.rng.shuffle(owned)
            for src in owned:
                if src.ships<C.ATTACK_THRESHOLD:continue
                enemies=[self.systems[n] for n in self.neighbors[src.id] if self.systems[n].owner_id!=e.id]
                if not enemies:continue
                target=min(enemies,key=lambda s:s.ships)
                if src.ships/max(1,target.ships)<1.25 and self.rng.random()>.12:continue
                self.launch(src.id,target.id,C.SEND_FRACTION)
    def launch(self,a,b,fraction):
        s=self.systems[a]
        if b not in self.neighbors[a] or s.owner_id is None:return
        n=math.floor(s.ships*fraction)
        if n<1:return
        s.ships-=n;self.fleets.append(Fleet(s.owner_id,a,b,float(n)))
    def arrive(self,f):
        t=self.systems[f.target_id]
        if t.owner_id==f.owner_id:t.ships+=f.ships
        elif f.ships>t.ships:t.owner_id=f.owner_id;t.ships=f.ships-t.ships
        else:t.ships=max(0,t.ships-f.ships)
    def winner(self):
        alive=[e for e in self.empires if e.alive];return alive[0] if len(alive)==1 else None
    def system_at(self,pos):
        p=pygame.Vector2(pos); found=[s for s in self.systems if s.pos.distance_to(p)<=15];return min(found,key=lambda s:s.pos.distance_to(p)) if found else None
