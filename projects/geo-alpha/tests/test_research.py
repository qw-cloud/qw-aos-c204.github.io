import unittest
from datetime import datetime, timedelta, timezone
from geoalpha.research import simulate, trend_baseline, satellite_signals, satellite_backtest


def bars(count=100,start=datetime(2024,5,20,tzinfo=timezone.utc)):
    out=[]
    for i in range(count):
        d=start+timedelta(days=i)
        if d.weekday()>4:continue
        price=100+i
        out.append({'date':d.date().isoformat(),'session_open_at':d.replace(hour=13,minute=30).isoformat(),
                    'session_close_at':d.replace(hour=20).isoformat(),'open':price,'close':price+1})
    return out


class ResearchAccountingTests(unittest.TestCase):
    def test_cash_only_is_zero_not_missing(self):
        b=bars(15);r=simulate(b,[0]*len(b))
        self.assertEqual(r['metrics']['net_return'],0)
        self.assertEqual(r['metrics']['max_drawdown'],0)
        self.assertIsNone(r['metrics']['win_rate'])
        self.assertIsNone(r['metrics']['sharpe'])

    def test_both_sides_of_cost_count(self):
        b=[{'date':'2024-05-20','session_open_at':'2024-05-20T13:30:00Z','session_close_at':'2024-05-20T20:00:00Z','open':100,'close':110},
           {'date':'2024-05-21','session_open_at':'2024-05-21T13:30:00Z','session_close_at':'2024-05-21T20:00:00Z','open':110,'close':120}]
        r=simulate(b,[1,1],round_trip_cost_bps=20)
        self.assertAlmostEqual(r['metrics']['net_return'],1.2*.999/1.001-1)
        self.assertEqual(r['metrics']['closed_trades'],1)
        self.assertTrue(r['trades'][0]['forced_end'])

    def test_daily_drawdown_sees_open_trade_losses(self):
        b=bars(7);b[1]['close']=80;b[2]['close']=90
        r=simulate(b,[1]*len(b),round_trip_cost_bps=0)
        self.assertLess(r['metrics']['max_drawdown'],-.20)

    def test_higher_costs_reduce_results(self):
        b=bars(15);targets=[i%2 for i in range(len(b))]
        low=simulate(b,targets,round_trip_cost_bps=5)['metrics']['net_return']
        high=simulate(b,targets,round_trip_cost_bps=50)['metrics']['net_return']
        self.assertGreater(low,high)

    def test_future_closes_do_not_change_earlier_trend_decisions(self):
        b=bars(120);first=trend_baseline(b)
        changed=[dict(x) for x in b];changed[-1]['close']=1
        second=trend_baseline(changed)
        self.assertEqual(first['curve'][:-1],second['curve'][:-1])

    def test_warmup_is_required(self):
        self.assertEqual(trend_baseline(bars(50))['status'],'insufficient_history')

    def test_no_leverage_or_short_assumption(self):
        b=bars(15)
        with self.assertRaises(ValueError):simulate(b,[2]*len(b))

    def history(self):
        obs={}
        for region in ('iowa','illinois'):
            for year,val in ((2023,.7),(2024,.5)):
                obs[f'{region}:{year}:5']={'region_id':region,'year':year,'month':5,'status':'usable',
                    'median_ndvi':val,'decision_at':f'{year}-05-20T23:59:00Z',
                    'assumed_available_at':f'{year}-05-19T12:00:00Z','item_id':f'{region}-{year}'}
        return {'observations':obs}

    def test_two_regions_and_same_month_required(self):
        h=self.history();signals,decisions=satellite_signals(h)
        self.assertEqual(len(signals),2)
        self.assertEqual(len(decisions),1)
        del h['observations']['illinois:2023:5']
        self.assertEqual(satellite_signals(h)[0],[])

    def test_historical_late_catalog_is_excluded(self):
        h=self.history();h['observations']['iowa:2024:5']['assumed_available_at']='2024-05-21T12:00:00Z'
        self.assertEqual(satellite_signals(h)[0],[])

    def test_satellite_direction_cannot_fill_before_decision(self):
        b=bars(40);signals,_=satellite_signals(self.history())
        r=satellite_backtest(b,signals,'CORN')
        self.assertEqual(r['trades'][0]['entry_at'],b[1]['session_open_at'])
        self.assertEqual(r['trades'][0]['exit_at'],b[11]['session_open_at'])

if __name__=='__main__':unittest.main()
