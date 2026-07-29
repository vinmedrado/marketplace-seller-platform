import React, { ReactElement, ReactNode } from 'react';

type Datum = Record<string, any>;
type ChartProps = { data?: Datum[]; children?: ReactNode; margin?: any };
type SeriesProps = { dataKey?: string; fill?: string; stroke?: string; name?: string; radius?: any };

function series(children: ReactNode, component: React.ComponentType<any>): SeriesProps[] {
  return React.Children.toArray(children)
    .filter((child): child is ReactElement<SeriesProps> => React.isValidElement(child) && child.type === component)
    .map((child) => child.props);
}

function numeric(data: Datum[], key = 'value') {
  return data.map((item) => Number(item[key] || 0));
}

export function ResponsiveContainer({ children, height = '100%', width = '100%' }: any) {
  return <div style={{ width, height, minHeight: 120 }}>{children}</div>;
}

export function BarChart({ data = [], children }: ChartProps) {
  const bars = series(children, Bar);
  const keys = bars.map((bar) => bar.dataKey || 'value');
  const values = keys.flatMap((key) => numeric(data, key));
  const max = Math.max(...values, 1);
  const groupWidth = 100 / Math.max(data.length, 1);
  const barWidth = Math.min(12, groupWidth * .7 / Math.max(bars.length, 1));
  return <svg viewBox="0 0 100 48" preserveAspectRatio="none" role="img" aria-label="Gráfico de barras">
    {[12, 24, 36].map((y) => <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="rgba(148,163,184,.12)" strokeWidth=".25" />)}
    {data.flatMap((item, index) => bars.map((bar, barIndex) => {
      const value = Number(item[bar.dataKey || 'value'] || 0);
      const barHeight = Math.max(0, (value / max) * 42);
      const x = index * groupWidth + groupWidth / 2 - (bars.length * barWidth) / 2 + barIndex * barWidth;
      return <rect key={`${index}-${barIndex}`} x={x} y={45 - barHeight} width={barWidth * .8} height={barHeight} rx="1" fill={bar.fill || '#38bdf8'} />;
    }))}
  </svg>;
}

export function LineChart({ data = [], children }: ChartProps) {
  const lines = series(children, Line);
  return <svg viewBox="0 0 100 48" preserveAspectRatio="none" role="img" aria-label="Gráfico de linhas">
    {[12, 24, 36].map((y) => <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="rgba(148,163,184,.12)" strokeWidth=".25" />)}
    {lines.map((line, lineIndex) => {
      const values = numeric(data, line.dataKey);
      const min = Math.min(...values, 0);
      const max = Math.max(...values, 1);
      const range = Math.max(max - min, 1);
      const path = values.map((value, index) => {
        const x = data.length <= 1 ? 50 : index * (100 / (data.length - 1));
        const y = 44 - ((value - min) / range) * 38;
        return `${index ? 'L' : 'M'}${x},${y}`;
      }).join(' ');
      return <path key={lineIndex} d={path} fill="none" stroke={line.stroke || '#38bdf8'} strokeWidth="1.2" vectorEffect="non-scaling-stroke" />;
    })}
  </svg>;
}

export function RadarChart({ data = [], children }: ChartProps) {
  const radar = series(children, Radar)[0] || {};
  const values = numeric(data, radar.dataKey);
  const max = Math.max(...values, 100);
  const center = 50;
  const radius = 36;
  const points = values.map((value, index) => {
    const angle = (Math.PI * 2 * index / Math.max(values.length, 1)) - Math.PI / 2;
    const length = radius * value / max;
    return `${center + Math.cos(angle) * length},${center + Math.sin(angle) * length}`;
  }).join(' ');
  const grid = [1, .66, .33].map((scale) => data.map((_, index) => {
    const angle = (Math.PI * 2 * index / Math.max(data.length, 1)) - Math.PI / 2;
    return `${center + Math.cos(angle) * radius * scale},${center + Math.sin(angle) * radius * scale}`;
  }).join(' '));
  return <svg viewBox="0 0 100 100" role="img" aria-label="Gráfico radar">
    {grid.map((polygon, index) => <polygon key={index} points={polygon} fill="none" stroke="rgba(148,163,184,.2)" strokeWidth=".5" />)}
    <polygon points={points} fill={radar.fill || '#8b5cf6'} fillOpacity=".25" stroke={radar.stroke || '#8b5cf6'} strokeWidth="1.2" />
  </svg>;
}

export function Bar(_: SeriesProps) { return null; }
export function Line(_: SeriesProps & Record<string, any>) { return null; }
export function Radar(_: SeriesProps & Record<string, any>) { return null; }
export function Tooltip(_: any) { return null; }
export function XAxis(_: any) { return null; }
export function YAxis(_: any) { return null; }
export function PolarGrid(_: any) { return null; }
export function PolarAngleAxis(_: any) { return null; }
export function PolarRadiusAxis(_: any) { return null; }
