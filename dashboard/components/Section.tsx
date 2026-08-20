import type { ReactNode } from "react";

export default function Section({
  id,
  eyebrow,
  title,
  description,
  aside,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  description?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="section-shell scroll-mt-6">
      <div className="section-head">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {aside ? <div>{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}
