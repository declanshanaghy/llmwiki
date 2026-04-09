'use client'

import * as React from 'react'
import { useTheme } from 'next-themes'

const LIGHT_INIT = `%%{init: {"flowchart": {"padding": 15, "nodeSpacing": 30, "rankSpacing": 40},"theme": "base", "themeVariables": {"primaryColor": "#e2e8f0", "primaryTextColor": "#1a202c", "primaryBorderColor": "#a0aec0", "lineColor": "#718096", "secondaryColor": "#ebf4ff", "tertiaryColor": "#e2e8f0", "noteTextColor": "#1a202c", "noteBkgColor": "#ebf4ff", "noteBorderColor": "#a0aec0", "edgeLabelBackground": "transparent", "clusterBkg": "#f7fafc", "clusterBorder": "#a0aec0", "actorTextColor": "#1a202c", "actorBkg": "#e2e8f0", "actorBorder": "#a0aec0", "signalColor": "#718096", "signalTextColor": "#1a202c", "activationBkgColor": "#ebf4ff", "activationBorderColor": "#a0aec0", "fontSize": "14px"}}}%%`

const DARK_INIT = `%%{init: {"flowchart": {"padding": 15, "nodeSpacing": 30, "rankSpacing": 40},"theme": "dark", "themeVariables": {"darkMode": true, "background": "#0C0A09", "primaryColor": "#2d3748", "primaryTextColor": "#F5F0EB", "primaryBorderColor": "#4a5568", "lineColor": "#78716C", "secondaryColor": "#1a365d", "tertiaryColor": "#2a4365", "noteTextColor": "#F5F0EB", "noteBkgColor": "#2d3748", "noteBorderColor": "#4a5568", "edgeLabelBackground": "transparent", "clusterBkg": "#1a202c", "clusterBorder": "#4a5568", "actorTextColor": "#F5F0EB", "actorBkg": "#2d3748", "actorBorder": "#4a5568", "signalColor": "#78716C", "signalTextColor": "#F5F0EB", "activationBkgColor": "#1a365d", "activationBorderColor": "#4a5568", "fontSize": "14px"}}}%%`

// Strip any existing %%{init:...}%% block from the chart so we can inject our own
function stripInit(chart: string): string {
  return chart.replace(/%%\{init:[\s\S]*?\}%%\s*/g, '').trim()
}

// Component color mappings: light hex -> dark hex
// Authors use light-mode colors in style directives; we remap for dark mode
const COLOR_LIGHT_TO_DARK: Record<string, string> = {
  // Products
  '#00CCCC': '#009999', '#009999': '#007777',  // Stream (teal)
  '#66CC33': '#4da626',                         // Edge (lime)
  '#0B6CD9': '#2980D6', '#0958B3': '#1a6fbd',  // Search (blue)
  '#008080': '#006666',                         // Lake (comp teal)
  // Control Plane
  '#FF6600': '#CC5200', '#CC5200': '#993d00',  // Zeus (orange)
  '#FF944D': '#CC7640',                         // Maestro
  '#CC190A': '#991307',                         // Auth0 (red)
  '#00CC99': '#009973',                         // Billing (emerald)
  '#D98C0B': '#B37309',                         // Admin (gold)
  // Infrastructure
  '#8B5CF6': '#7C3AED',                         // Typhon (purple)
  '#A78BFA': '#8B6FD9',                         // CI/CD
  '#64748B': '#4B5563',                         // ECS/EKS (slate)
  '#94A3B8': '#6B7A8D',                         // CloudFormation
  '#475569': '#374151',                         // VPC
  '#059669': '#047857',                         // S3
  '#EC4899': '#BE185D',                         // Monitoring (pink)
  // Concepts
  '#E8E8E8': '#333333', '#D8D8D8': '#444444',
  '#CCCCCC': '#555555', '#F8F8F8': '#1A1A1A',
}

// Also remap text colors for dark mode
const TEXT_LIGHT_TO_DARK: Record<string, string> = {
  '#000000': '#F5F0EB', '#000': '#F5F0EB',
  '#666666': '#999999',
}

function remapColorsForDark(chart: string): string {
  let result = chart
  // Remap fill and stroke colors
  for (const [light, dark] of Object.entries(COLOR_LIGHT_TO_DARK)) {
    result = result.replaceAll(light, dark)
  }
  // Remap text colors (color: values)
  for (const [light, dark] of Object.entries(TEXT_LIGHT_TO_DARK)) {
    result = result.replaceAll(`color:${light}`, `color:${dark}`)
  }
  return result
}

export function MermaidBlock({ chart }: { chart: string }) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const renderIdRef = React.useRef(0)
  const { theme } = useTheme()

  React.useEffect(() => {
    let cancelled = false
    const renderId = ++renderIdRef.current

    import('mermaid').then(({ default: mermaid }) => {
      if (cancelled) return

      const isDark = theme === 'dark'
      const initBlock = isDark ? DARK_INIT : LIGHT_INIT
      let cleanChart = stripInit(chart)
      if (isDark) cleanChart = remapColorsForDark(cleanChart)
      const themedChart = `${initBlock}\n${cleanChart}`

      // Each render needs a unique ID
      const id = `mermaid-${renderId}-${Math.random().toString(36).slice(2, 9)}`

      mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', flowchart: { htmlLabels: false } })
      mermaid
        .render(id, themedChart)
        .then(({ svg }) => {
          if (!cancelled && containerRef.current) {
            containerRef.current.innerHTML = svg
          }
        })
        .catch(() => {
          if (!cancelled && containerRef.current) {
            containerRef.current.textContent = chart
          }
        })
    })

    return () => { cancelled = true }
  }, [chart, theme])

  return (
    <div
      ref={containerRef}
      className="my-6 flex justify-center [&_svg]:max-w-full"
    />
  )
}
