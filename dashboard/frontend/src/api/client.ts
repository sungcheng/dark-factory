import type { JobSummary, JobDetail, Event } from "../types";

const BASE_URL = "/api/v1";

/**
 * Fetch all jobs (summaries only)
 */
export async function getJobs(): Promise<JobSummary[]> {
  const response = await fetch(`${BASE_URL}/jobs`);
  const data = await response.json();
  return data.jobs;
}

/**
 * Fetch a single job with full details and event history
 */
export async function getJob(jobId: string): Promise<JobDetail> {
  const response = await fetch(`${BASE_URL}/jobs/${jobId}`);
  return response.json();
}

/**
 * Fetch live event stream for a job
 */
export async function getJobLog(jobId: string): Promise<Event[]> {
  const response = await fetch(`${BASE_URL}/jobs/${jobId}/log`);
  const data = await response.json();
  return data.events;
}
