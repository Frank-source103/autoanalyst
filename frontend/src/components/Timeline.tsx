import React, { useEffect, useRef, useState } from 'react';
import { AgentEvent } from '../types';
import { EventCard } from './EventCard';

interface TimelineProps {
  events: AgentEvent[];
}

export const Timeline: React.FC<TimelineProps> = ({ events }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);

  const scrollToBottom = (smooth = true) => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
      });
      setUserScrolledUp(false);
    }
  };

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    // If user is more than 100px from the bottom, mark as scrolled up
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
    setUserScrolledUp(!isAtBottom);
  };

  useEffect(() => {
    if (!userScrolledUp) {
      scrollToBottom(true);
    }
  }, [events, userScrolledUp]);

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <h2 className="timeline-title">Execution Timeline</h2>
        <span className="event-count-badge">{events.length}</span>
      </div>

      <div
        className="timeline-scroll-area"
        ref={containerRef}
        onScroll={handleScroll}
      >
        {events.length === 0 ? (
          <div className="timeline-empty-state">
            <span className="empty-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </span>
            <p>Awaiting execution start. Submit question to initiate autonomous analysis.</p>
          </div>
        ) : (
          events.map((evt) => <EventCard key={`${evt.run_id}-${evt.seq}`} event={evt} />)
        )}
      </div>

      {userScrolledUp && (
        <button className="jump-to-latest-btn" onClick={() => scrollToBottom(true)}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="6 9 12 15 18 9" />
          </svg>
          Jump to latest
        </button>
      )}
    </div>
  );
};
