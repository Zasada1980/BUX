import { useMemo } from 'react';
import { Calendar, momentLocalizer, Event } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';

// Setup localizer for calendar
const localizer = momentLocalizer(moment);

interface Shift {
  id: number;
  worker_name: string;
  start_time: string;
  end_time: string | null;
  status: 'open' | 'completed' | 'cancelled';
  duration_minutes: number | null;
}

interface ShiftsCalendarProps {
  shifts: Shift[];
  onSelectEvent?: (event: CalendarEvent) => void;
}

interface CalendarEvent extends Event {
  id: number;
  title: string;
  start: Date;
  end: Date;
  resource: {
    status: string;
    workerName: string;
  };
}

export default function ShiftsCalendar({ shifts, onSelectEvent }: ShiftsCalendarProps) {
  // Transform shifts into calendar events
  const events: CalendarEvent[] = useMemo(() => {
    return shifts.map((shift) => {
      const start = new Date(shift.start_time);
      const end = shift.end_time ? new Date(shift.end_time) : new Date(start.getTime() + 8 * 60 * 60 * 1000); // Default 8h if open
      
      return {
        id: shift.id,
        title: `${shift.worker_name} - ${shift.status}`,
        start,
        end,
        resource: {
          status: shift.status,
          workerName: shift.worker_name
        }
      };
    });
  }, [shifts]);

  // Custom event styling based on status
  const eventStyleGetter = (event: CalendarEvent) => {
    let backgroundColor = '#3b82f6'; // default blue
    
    switch (event.resource.status) {
      case 'completed':
        backgroundColor = '#10b981'; // green
        break;
      case 'cancelled':
        backgroundColor = '#ef4444'; // red
        break;
      case 'open':
        backgroundColor = '#3b82f6'; // blue
        break;
    }

    return {
      style: {
        backgroundColor,
        borderRadius: '4px',
        opacity: 0.9,
        color: 'white',
        border: '0',
        display: 'block',
        fontSize: '0.875rem',
        padding: '2px 5px'
      }
    };
  };

  return (
    <div style={{ height: '600px', background: 'white', padding: '1rem', borderRadius: '0.5rem', border: '1px solid #e5e7eb' }}>
      <Calendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        style={{ height: '100%' }}
        eventPropGetter={eventStyleGetter}
        onSelectEvent={onSelectEvent}
        views={['month', 'week', 'day']}
        defaultView="week"
        popup
        tooltipAccessor={(event: CalendarEvent) => {
          const duration = Math.round((event.end.getTime() - event.start.getTime()) / 1000 / 60);
          return `${event.resource.workerName}\nStatus: ${event.resource.status}\nDuration: ${duration}m`;
        }}
      />
    </div>
  );
}
