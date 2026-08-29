'use client';
import { useEffect, useState } from "react";
import { Card } from '@/components/ui/card';
import { Info } from 'lucide-react';
import { useLanguage } from '@/context/LanguageContext';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
  ComposedChart,
} from 'recharts';
import { TrendingUp, TrendingDown, Target, AlertCircle } from 'lucide-react';

export default function MarketIntelligence() {
  const { t } = useLanguage();

  let lastMonth = "";
  const [kpis, setKpis] = useState<any>(null);
  const [priceSeries, setPriceSeries] = useState<any[]>([]);
  const [demandSupply, setDemandSupply] = useState<any[]>([]);
  const [locationPrices, setLocationPrices] = useState<any[]>([]);
  const [marketInsight, setMarketInsight] = useState<any>(null);

  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    fetch(`${API_URL}/api/market/kpis`)
      .then(res => res.json())
      .then(setKpis);

    fetch(`${API_URL}/api/market/price-series`)
      .then(res => res.json())
      .then(setPriceSeries);

    fetch(`${API_URL}/api/market/demand-volatility`)
      .then(res => res.json())
      .then(setDemandSupply);
      
    fetch(`${API_URL}/api/market/location-price-summary`)
      .then(res => res.json())
      .then(setLocationPrices);
      
    fetch(`${API_URL}/api/market/insight`)
      .then(res => res.json())
      .then(setMarketInsight);
  }, []);

  const demandIndexLegend = [
    { range: "0–20", color: "bg-blue-500", label: t('veryLowDemand') },
    { range: "20–40", color: "bg-green-500", label: t('mildDemand') },
    { range: "40–60", color: "bg-yellow-500", label: t('moderateDemand') },
    { range: "60–80", color: "bg-orange-500", label: t('highDemand') },
    { range: "80–100", color: "bg-red-500", label: t('veryStrongDemand') },
  ];

  const DemandIndexTooltip = () => (
    <div className="space-y-2 text-xs">
      <p className="font-semibold text-foreground mb-1">
        {t('marketDemandIndexRange')}
      </p>

      {demandIndexLegend.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${item.color}`} />
          <span className="text-muted-foreground w-14">{item.range}</span>
          <span className="text-foreground">{item.label}</span>
        </div>
      ))}
    </div>
  );

  const VolatilityTooltip = () => (
    <div className="space-y-2 text-xs">
      <p className="font-semibold text-foreground mb-1">
        {t('priceVolatilityPercent')}
      </p>

      <p className="text-muted-foreground">
        {t('volatilityDesc')}
      </p>

      <div className="space-y-1 pt-1">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-muted-foreground w-14">&lt; 2%</span>
          <span className="text-foreground">{t('stablePrices')}</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-yellow-500" />
          <span className="text-muted-foreground w-14">2–5%</span>
          <span className="text-foreground">{t('moderateVolatility')}</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-muted-foreground w-14">&gt; 5%</span>
          <span className="text-foreground">{t('highInstability')}</span>
        </div>
      </div>

      <p className="text-muted-foreground pt-1">
        {t('volatilityChangeDesc')}
      </p>
    </div>
  );

  const chartData = [...priceSeries]
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .map((d, index) => ({
      index, // 👈 THIS IS THE KEY
      date: d.date,
      actual_price: d.type === "actual" ? d.price : null,
      forecast_price: d.type === "forecast" ? d.price : null,
    }));

  const sortedDemandData = [...demandSupply].sort(
    (a, b) => new Date(a.month).getTime() - new Date(b.month).getTime()
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-foreground">{t('marketIntelligence')}</h2>
        <p className="text-muted-foreground mt-1">{t('marketIntelligenceDesc')}</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            key: 'current_price',
            label: t('currentMarketPrice'),
            value: kpis ? `₹${kpis.current_price}/kg` : '—',
            icon: TrendingUp,
            change: kpis ? `${kpis.price_change_pct}%` : '—',
            status: kpis && kpis.price_change_pct >= 0 ? 'up' : 'down',
          },
          {
            key: 'forecast_price',
            label: t('sevenDayForecast'),
            value: kpis ? `₹${kpis.forecast_price}/kg` : '—',
            icon: Target,
            change: kpis ? `${(((kpis.forecast_price - kpis.current_price) / kpis.current_price) * 100).toFixed(1)}%` : '—',
            status: kpis && kpis.forecast_price > kpis.current_price ? 'up' : 'down',
          },
          {
            key: 'demand_index',
            label: t('marketDemandIndex'),
            value: kpis ? `${kpis.market_demand} / 100` : '—',
            icon: TrendingUp,
            change: kpis ? `${kpis.market_demand_change_abs} pts` : '—',
            status: kpis && kpis.market_demand_change_abs >= 0 ? 'up' : 'down',
            isDemand: true,
          },
          {
            key: 'volatility',
            label: t('priceVolatility'),
            value: kpis ? `${kpis.volatility}%` : '—',
            icon: AlertCircle,
            change: kpis ? `${kpis.volatility_change_abs} pts` : '—',
            status: kpis && kpis.volatility_change_abs <= 0 ? 'up' : 'down',
            isVolatility: true,
          },
        ].map((item, idx) => {
          const Icon = item.icon;
          return (
            <Card key={idx} className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <span>{item.label}</span>

                    {(item.isDemand || item.isVolatility) && (
                      <div className="relative group">
                        <Info className="h-3.5 w-3.5 text-muted-foreground cursor-pointer" />

                        {/* Tooltip */}
                        <div className="absolute z-50 hidden group-hover:block top-5 left-0 w-64 rounded-lg bg-background border border-border p-3 shadow-lg">
                          {item.isDemand ? (
                            <DemandIndexTooltip />
                          ) : (
                            <VolatilityTooltip />
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  <p className="text-2xl font-bold text-foreground mt-2">{item.value}</p>
                  <p
                    className={`text-xs mt-2 ${item.status === 'up'
                      ? 'text-green-600 dark:text-green-400'
                      : item.status === 'down'
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-blue-600 dark:text-blue-400'
                      }`}
                  >
                    {item.change} {t('vsLastWeek')}
                  </p>
                </div>
                <Icon className="h-6 w-6 text-primary opacity-40" />
              </div>
            </Card>
          );
        })}
      </div>

      {/* Market Insight */}
      {marketInsight && (
        <Card
          className={`p-4 flex items-start gap-3 border-l-4 ${marketInsight.signal === 'opportunity'
            ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
            : marketInsight.signal === 'risk'
              ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
              : 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
            }`}
        >
          <TrendingUp className="h-5 w-5 mt-0.5 flex-shrink-0 text-foreground opacity-70" />

          <div>
            <h3 className="font-semibold text-foreground">
              {marketInsight.title}
            </h3>

            {/* Rule-based insight */}
            <p className="text-sm text-muted-foreground mt-1">
              {marketInsight.message}
            </p>

            {/* AI Insight */}
            {marketInsight.ai_message && (
              <p className="text-sm text-muted-foreground mt-2 italic">
                <span className="font-medium not-italic">{t('aiInsight')}:</span>{" "}
                {marketInsight.ai_message}
              </p>
            )}
          </div>
        </Card>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Price History & Forecast */}
        <Card className="p-6">
          <h3 className="font-semibold text-foreground mb-4">{t('priceTrendForecast')}</h3>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={chartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#16a34a" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                type="category"
                interval={0}
                tickFormatter={(value) => {
                  const [year, month] = value.split("-");
                  const label = `${month}/${year.slice(2)}`;

                  // show label only when month changes
                  if (label === lastMonth) return "";
                  lastMonth = label;
                  return label;
                }}
              />
              <YAxis />

              <Tooltip />
              <Legend />

              <ReferenceLine
                x={chartData.find(d => d.forecast_price !== null)?.date}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={t('forecast')}
              />

              {/* Actual price (Area) */}
              <Area
                type="monotone"
                dataKey="actual_price"
                stroke="#16a34a"
                fill="url(#colorPrice)"
                strokeWidth={2}
                dot={false}
                name={t('actualPrice')}
              />

              {/* Forecast price (Line) */}
              <Line
                type="monotone"
                dataKey="forecast_price"
                stroke="#2563eb"
                strokeDasharray="6 4"
                strokeWidth={2}
                dot={{ r: 3 }}
                name={t('forecastPrice')}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        {/* Demand vs Supply */}
        <Card className="p-6">
          <h3 className="font-semibold text-foreground mb-4">{t('demandVsVolatility')}</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={sortedDemandData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />

              <XAxis dataKey="month" stroke="#6b7280" />

              {/* Left axis for Demand */}
              <YAxis
                yAxisId="left"
                stroke="#35a857"
              />

              {/* Right axis for Volatility */}
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="#f59e0b"
                tickFormatter={(v) => `${v}%`}
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#f3f4f6',
                }}
                formatter={(value, name) =>
                  name === t('marketVolatilityPercent')
                    ? [`${value}%`, name]
                    : [value, name]
                }
              />

              <Legend />

              {/* Demand bar */}
              <Bar
                yAxisId="left"
                dataKey="demand"
                fill="#35a857"
                name={t('demandIndex')}
              />

              {/* Volatility bar */}
              <Bar
                yAxisId="right"
                dataKey="volatility"
                fill="#f59e0b"
                name={t('marketVolatilityPercent')}
              />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Location-wise Price Comparison */}
      <Card className="p-6">
        <h3 className="font-semibold text-foreground mb-4">
          {t('locationWisePriceComparison')}
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-3 px-4 text-sm text-muted-foreground">
                  {t('locationCol')}
                </th>
                <th className="text-left py-3 px-4 text-sm text-muted-foreground">
                  {t('avgPriceRupees')}
                </th>
                <th className="text-left py-3 px-4 text-sm text-muted-foreground">
                  {t('currentPriceRupees')}
                </th>
                <th className="text-left py-3 px-4 text-sm text-muted-foreground">
                  {t('priceRangeRupees')}
                </th>
                <th className="text-left py-3 px-4 text-sm text-muted-foreground">
                  {t('trendCol')}
                </th>
              </tr>
            </thead>

            <tbody>
              {locationPrices.map((row, idx) => (
                <tr
                  key={idx}
                  className="border-b border-border hover:bg-muted/50 transition-colors"
                >
                  <td className="py-3 px-4 font-medium text-foreground">
                    {row.location}
                  </td>

                  <td className="py-3 px-4 text-foreground">
                    ₹{row.avgPrice}
                  </td>

                  <td className="py-3 px-4 text-foreground">
                    ₹{row.currentPrice}
                  </td>

                  <td className="py-3 px-4 text-foreground">
                    ₹{row.minPrice} – ₹{row.maxPrice}
                  </td>

                  <td className="py-3 px-4">
                    {row.trend === 'up' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                        <TrendingUp className="h-4 w-4" />
                        {t('rising')}
                      </span>
                    )}

                    {row.trend === 'down' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">
                        <TrendingDown className="h-4 w-4" />
                        {t('falling')}
                      </span>
                    )}

                    {row.trend === 'stable' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                        {t('stableTrend')}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-sm text-muted-foreground mt-4">
          {t('locationTableDesc')}
        </p>
      </Card>

      {/* Recommendations */}
      {marketInsight?.ai_recommendations?.length > 0 && (
        <Card className="p-6 border-l-4 border-primary">
          <h3 className="font-semibold text-foreground mb-3">
            {t('aiStrategyRecommendations')}
          </h3>

          <ul className="space-y-2 text-sm text-muted-foreground">
            {marketInsight.ai_recommendations.map((rec: string, idx: number) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-primary font-bold mt-0.5">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
