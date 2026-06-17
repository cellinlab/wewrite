"use client";

import { PlatformVersion } from "@/lib/api";
import { Card, Badge, Button, Tooltip } from "@/components/ui";

export default function PlatformVersions({ versions }: { versions: PlatformVersion[] }) {
  if (!versions?.length) return null;
  return (
    <div className="grid gap-3">
      {versions.map((v) => (
        <Card key={v.platform}>
          <div className="flex items-center gap-2 flex-wrap">
            <strong>{v.label}</strong>
            {v.status === "failed" ? (
              <Badge tone="warn">未产出</Badge>
            ) : (
              <Tooltip content="相似度 = 与源内容的字符 3-gram Jaccard，越低越原创">
                <Badge tone={v.passed ? "ok" : "warn"}>
                  {v.max_similarity != null
                    ? `相似度 ${Math.round(v.max_similarity * 100)}%`
                    : ""}
                  {v.humanness != null
                    ? ` · 拟人 ${Math.round(v.humanness * 100)}%`
                    : ""}
                  {v.passed ? "" : " · 待微调"}
                </Badge>
              </Tooltip>
            )}
          </div>
          {v.warning && <p className="mt-2 text-sm text-muted">{v.warning}</p>}
          {v.status !== "failed" && (
            <>
              <pre className="mt-3 whitespace-pre-wrap rounded-md bg-surface-2 p-3 text-xs text-text max-h-[360px] overflow-auto">
                {v.markdown}
              </pre>
              <Button
                size="sm"
                variant="ghost"
                className="mt-2"
                onClick={() => navigator.clipboard.writeText(v.markdown)}
              >
                复制
              </Button>
            </>
          )}
        </Card>
      ))}
    </div>
  );
}
