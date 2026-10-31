"""Small, reproducible multi-station, multi-line discrete-event *reference*.
Arrival/service times and failure delays are simulated; no PLC, Isaac Sim or SimPy coupling.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from random import Random

@dataclass(frozen=True)
class StationConfig:
    name:str
    service_mean_s:float
    capacity:int=1
    downtime_probability:float=0.0
    downtime_s:float=0.0


def run_line(n=100,seed=2026,stations=None,arrival_every_s=8.0,lines=1):
    if stations is None:
        stations=[StationConfig('3D_Print',18,1,.03,25),StationConfig('Phone_Vision',5),StationConfig('Pi_Vision',6),
                  StationConfig('Metrology',7),StationConfig('Assembly',9),StationConfig('Sorting',3)]
    if n<1 or lines<1 or arrival_every_s<=0:raise ValueError('bad simulation size')
    for s in stations:
        if s.capacity<1 or s.service_mean_s<=0 or not 0<=s.downtime_probability<=1 or s.downtime_s<0:
            raise ValueError('invalid station config')
    rng=Random(seed)
    # Local capacities and queues: each line independent, each station has C servers.
    free={(line,s.name):[0.0]*s.capacity for line in range(lines) for s in stations}
    busy={(line,s.name):0.0 for line in range(lines) for s in stations}
    observations=[]
    for i in range(n):
        lane=i%lines;arrival=i*arrival_every_s
        t=arrival
        trace=[]
        for station in stations:
            servers=free[(lane,station.name)]
            server=min(range(len(servers)),key=lambda k:servers[k])
            start=max(t,servers[server])
            service=max(0.05,rng.lognormvariate(0,0.16)*station.service_mean_s)
            downtime=(rng.random()<station.downtime_probability)
            end=start+service+(station.downtime_s if downtime else 0)
            servers[server]=end
            busy[(lane,station.name)]+=service
            trace.append(dict(station=station.name,arrival=round(t,5),start=round(start,5),end=round(end,5),
                              queue_wait_s=round(start-t,5),downtime=downtime))
            t=end
        observations.append({'specimen_id':f'V-{i:05d}','line_id':lane,'arrival':round(arrival,5),'finish':round(t,5),
                             'cycle_time_s':round(t-arrival,5),'station_trace':trace,'origin':'SIMULATED'})
    makespan=max(o['finish'] for o in observations)
    station_summary={f'{lane}:{s.name}':{'utilization':round(min(1,busy[(lane,s.name)]/(makespan*s.capacity)),5),
                                       'busy_time_s':round(busy[(lane,s.name)],4)}
                     for lane in range(lines) for s in stations}
    return {'generator':'flow_shop_reference_v1','origin':'SIMULATED','seed':seed,'completed':len(observations),
            'lines':lines,'makespan_s':round(makespan,4),'throughput_per_hour':round(n/makespan*3600,4),
            'mean_cycle_s':round(sum(o['cycle_time_s'] for o in observations)/n,5),
            'station_summary':station_summary,'sample_routes':observations[:min(10,n)]}
