import unittest
from datetime import datetime, timezone
from geoalpha.core import age_hours, build_alerts, compute_ndvi, geometry_bbox, parse, quality, replay
import numpy as np

CONFIG={"regions":[{"id":"gulf","exposure_bbox":[-98,24,-86,32]}],"assets":[{"symbol":"UNG","regions":["gulf"]}],
        "gates":{"event_max_age_hours":72,"nhc_max_age_hours":12,"satellite_max_age_days":14,"minimum_clear_fraction":.25}}
AT=datetime(2026,10,9,1,tzinfo=timezone.utc)

class IntegrityTests(unittest.TestCase):
    def test_utc_required(self):
        with self.assertRaises(ValueError):parse("2026-10-08T12:00:00")

    def test_clouds_do_not_become_vegetation(self):
        stats=compute_ndvi(np.array([[1000,1000]]),np.array([[4000,4000]]),np.array([[4,9]]),{}, {})
        self.assertEqual(stats['clear_fraction'],.5)
        self.assertIsNone(stats['grid'][0][1])
        self.assertAlmostEqual(stats['median_ndvi'],.6)

    def test_boa_offset_applied_only_once(self):
        a={"raster:bands":[{"scale":.0001,"offset":-.1}]}
        stats=compute_ndvi(np.array([[2000]]),np.array([[4000]]),np.array([[4]]),a,a,False)
        applied=compute_ndvi(np.array([[1000]]),np.array([[3000]]),np.array([[4]]),a,a,True)
        self.assertEqual(stats['median_ndvi'],applied['median_ndvi'])

    def test_stale_image_abstains(self):
        self.assertEqual(quality({"observed_at":"2026-09-01T12:00:00Z","clear_fraction":1,"median_ndvi":.5},CONFIG,AT),'stale')

    def test_future_image_abstains(self):
        self.assertEqual(quality({"observed_at":"2026-10-10T12:00:00Z","clear_fraction":1,"median_ndvi":.5},CONFIG,AT),'invalid_future_timestamp')

    def test_insufficient_coverage_abstains(self):
        self.assertEqual(quality({"observed_at":"2026-10-08T12:00:00Z","clear_fraction":.1,"median_ndvi":.5},CONFIG,AT),'insufficient_clear_pixels')

    def test_stale_and_unrelated_events_do_not_alert(self):
        events=[{"id":"old","observed_at":"2026-09-01T12:00:00Z","bbox":[-90,30,-90,30]},
                {"id":"far","observed_at":"2026-10-08T12:00:00Z","bbox":[10,40,10,40]}]
        self.assertEqual(build_alerts(CONFIG,{},events,[],AT),[])

    def test_storm_watch_does_not_assume_direction(self):
        event={"id":"storm","title":"test","observed_at":"2026-10-08T23:00:00Z","bbox":[-90,30,-90,30],"url":"https://www.nhc.noaa.gov/","source_kind":"official"}
        alerts=build_alerts(CONFIG,{},[],[event],AT)
        self.assertEqual(alerts[0]['symbols'],['UNG'])
        self.assertEqual(alerts[0]['direction'],0)

    def test_polygon_bounds(self):
        self.assertEqual(geometry_bbox({"coordinates":[[[-92,28],[-88,31],[-92,28]]]}),[-92,28,-88,31])

    def test_controlled_burn_does_not_become_supply_alert(self):
        event={"id":"burn","title":"Prescribed Fire","observed_at":"2026-10-08T23:00:00Z","bbox":[-90,30,-90,30]}
        self.assertEqual(build_alerts(CONFIG,{},[event],[],AT),[])

    def bars(self):
        return [{"session_open_at":f"2026-10-{day:02}T13:30:00Z","session_close_at":f"2026-10-{day:02}T20:00:00Z","open":100,"close":110} for day in (7,8,9)]

    def test_signal_after_open_cannot_fill_that_open(self):
        s=[{"symbol":"CORN","direction":1,"validated":True,"available_at":"2026-10-08T14:00:00Z"}]
        r=replay(s,self.bars(),'CORN',1,20)
        self.assertEqual(r['trades'][0]['entry_at'],'2026-10-09T13:30:00Z')
        self.assertAlmostEqual(r['net_return'],.098)

    def test_equal_time_requires_next_open(self):
        s=[{"symbol":"CORN","direction":1,"validated":True,"available_at":"2026-10-08T13:30:00Z"}]
        self.assertEqual(replay(s,self.bars(),'CORN',1)['trades'][0]['entry_at'],'2026-10-09T13:30:00Z')

    def test_unvalidated_and_watch_signals_never_make_performance(self):
        s=[{"symbol":"CORN","direction":1,"available_at":"2026-10-08T00:00:00Z"},
           {"symbol":"CORN","direction":0,"validated":True,"available_at":"2026-10-08T00:00:00Z"}]
        r=replay(s,self.bars(),'CORN',1)
        self.assertIsNone(r['net_return'])
        self.assertEqual(r['status'],'not_ready')

    def test_overlapping_signal_does_not_duplicate_positions(self):
        s=[{"symbol":"CORN","direction":1,"validated":True,"available_at":f"2026-10-07T{hour}:00:00Z"} for hour in ('10','11')]
        self.assertEqual(len(replay(s,self.bars(),'CORN',2)['trades']),1)

if __name__=='__main__':unittest.main()