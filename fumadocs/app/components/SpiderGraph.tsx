'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  isCenter?: boolean;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface SpiderGraphProps {
  entityId: string;
  entityType: string;
  depth?: number;
}

// Color mapping for entity types
const typeColors: Record<string, string> = {
  Host: '#3b82f6',      // blue
  VM: '#8b5cf6',        // purple
  Service: '#10b981',   // green
  Pod: '#06b6d4',       // cyan
  Network: '#f59e0b',   // amber
  Location: '#ec4899',  // pink
  Share: '#ef4444',     // red
  StoragePool: '#f97316', // orange
  NAS: '#84cc16',       // lime
  SmartDevice: '#eab308', // yellow
  ProxmoxNode: '#6366f1', // indigo
  RunbookDocument: '#14b8a6', // teal
  Alert: '#dc2626',     // red-600
  default: '#6b7280',   // gray
};

export default function SpiderGraph({ entityId, entityType, depth = 2 }: SpiderGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Fetch graph data
  useEffect(() => {
    setLoading(true);
    fetch(`/api/entities/${encodeURIComponent(entityId)}/graph?type=${entityType}&depth=${depth}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          // Initialize node positions in a circle around center
          const nodeCount = data.nodes?.length || 0;
          const centerX = 400;
          const centerY = 300;
          const radius = Math.min(200, 50 + nodeCount * 15);

          const initializedNodes = (data.nodes || []).map((node: GraphNode, i: number) => {
            if (node.isCenter) {
              return { ...node, x: centerX, y: centerY, vx: 0, vy: 0 };
            }
            const angle = (2 * Math.PI * i) / (nodeCount - 1 || 1);
            return {
              ...node,
              x: centerX + radius * Math.cos(angle),
              y: centerY + radius * Math.sin(angle),
              vx: 0,
              vy: 0,
            };
          });

          setNodes(initializedNodes);
          setEdges(data.edges || []);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [entityId, entityType, depth]);

  // Simple force simulation
  useEffect(() => {
    if (nodes.length === 0) return;

    let animationId: number;
    let iterations = 0;
    const maxIterations = 100;

    const simulate = () => {
      if (iterations >= maxIterations) return;

      setNodes((prevNodes) => {
        const newNodes = prevNodes.map((node) => ({ ...node }));
        const centerX = 400;
        const centerY = 300;

        // Apply forces
        for (let i = 0; i < newNodes.length; i++) {
          const node = newNodes[i];
          if (node.isCenter) continue;

          // Repulsion from other nodes
          for (let j = 0; j < newNodes.length; j++) {
            if (i === j) continue;
            const other = newNodes[j];
            const dx = (node.x || 0) - (other.x || 0);
            const dy = (node.y || 0) - (other.y || 0);
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = 1000 / (dist * dist);
            node.vx = (node.vx || 0) + (dx / dist) * force;
            node.vy = (node.vy || 0) + (dy / dist) * force;
          }

          // Attraction to connected nodes
          edges.forEach((edge) => {
            if (edge.source === node.id || edge.target === node.id) {
              const otherId = edge.source === node.id ? edge.target : edge.source;
              const other = newNodes.find((n) => n.id === otherId);
              if (other) {
                const dx = (other.x || 0) - (node.x || 0);
                const dy = (other.y || 0) - (node.y || 0);
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                node.vx = (node.vx || 0) + dx * 0.01;
                node.vy = (node.vy || 0) + dy * 0.01;
              }
            }
          });

          // Centering force
          node.vx = (node.vx || 0) + (centerX - (node.x || 0)) * 0.005;
          node.vy = (node.vy || 0) + (centerY - (node.y || 0)) * 0.005;

          // Apply velocity with damping
          node.x = (node.x || 0) + (node.vx || 0) * 0.1;
          node.y = (node.y || 0) + (node.vy || 0) * 0.1;
          node.vx = (node.vx || 0) * 0.9;
          node.vy = (node.vy || 0) * 0.9;

          // Boundary constraints
          node.x = Math.max(50, Math.min(750, node.x || 0));
          node.y = Math.max(50, Math.min(550, node.y || 0));
        }

        return newNodes;
      });

      iterations++;
      animationId = requestAnimationFrame(simulate);
    };

    animationId = requestAnimationFrame(simulate);
    return () => cancelAnimationFrame(animationId);
  }, [edges, nodes.length]);

  const getNodeColor = (type: string) => typeColors[type] || typeColors.default;

  const getNodeById = useCallback(
    (id: string) => nodes.find((n) => n.id === id),
    [nodes]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-800 rounded-lg">
        <div className="text-gray-400">Loading graph...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-800 rounded-lg">
        <div className="text-red-400">Error: {error}</div>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-800 rounded-lg">
        <div className="text-gray-400">No relationships found</div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Relationship Graph</h3>
        <div className="flex gap-2 flex-wrap">
          {Array.from(new Set(nodes.map((n) => n.type))).map((type) => (
            <span
              key={type}
              className="px-2 py-1 rounded text-xs"
              style={{ backgroundColor: getNodeColor(type), color: 'white' }}
            >
              {type}
            </span>
          ))}
        </div>
      </div>

      <svg
        ref={svgRef}
        viewBox="0 0 800 600"
        className="w-full h-96 bg-gray-900 rounded"
      >
        {/* Edges */}
        {edges.map((edge, i) => {
          const source = getNodeById(edge.source);
          const target = getNodeById(edge.target);
          if (!source || !target) return null;

          const isHighlighted =
            hoveredNode === edge.source || hoveredNode === edge.target;

          return (
            <g key={i}>
              <line
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={isHighlighted ? '#60a5fa' : '#4b5563'}
                strokeWidth={isHighlighted ? 2 : 1}
                opacity={isHighlighted ? 1 : 0.6}
              />
              {/* Edge label */}
              {isHighlighted && (
                <text
                  x={((source.x || 0) + (target.x || 0)) / 2}
                  y={((source.y || 0) + (target.y || 0)) / 2 - 5}
                  fontSize="10"
                  fill="#9ca3af"
                  textAnchor="middle"
                >
                  {edge.type}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const isHighlighted = hoveredNode === node.id;
          const radius = node.isCenter ? 25 : isHighlighted ? 20 : 15;

          return (
            <g
              key={node.id}
              transform={`translate(${node.x || 0}, ${node.y || 0})`}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              style={{ cursor: 'pointer' }}
            >
              <circle
                r={radius}
                fill={getNodeColor(node.type)}
                stroke={node.isCenter ? '#fff' : isHighlighted ? '#fff' : 'none'}
                strokeWidth={node.isCenter ? 3 : 2}
                opacity={isHighlighted || node.isCenter ? 1 : 0.8}
              />
              <text
                y={radius + 15}
                fontSize="11"
                fill="#e5e7eb"
                textAnchor="middle"
                fontWeight={node.isCenter ? 'bold' : 'normal'}
              >
                {(node.name || node.id || '').substring(0, 20)}
              </text>
              {isHighlighted && !node.isCenter && (
                <text y={radius + 28} fontSize="9" fill="#9ca3af" textAnchor="middle">
                  {node.type}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Node list for clicking */}
      <div className="mt-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
        {nodes
          .filter((n) => !n.isCenter)
          .slice(0, 12)
          .map((node) => (
            <Link
              key={node.id}
              href={`/entities/${encodeURIComponent(node.id)}?type=${node.type}`}
              className="px-3 py-2 bg-gray-700 rounded hover:bg-gray-600 text-sm truncate"
              style={{ borderLeft: `3px solid ${getNodeColor(node.type)}` }}
            >
              {node.name || node.id}
            </Link>
          ))}
        {nodes.length > 13 && (
          <div className="px-3 py-2 bg-gray-700 rounded text-sm text-gray-400">
            +{nodes.length - 13} more
          </div>
        )}
      </div>
    </div>
  );
}
