import { createClient } from '@supabase/supabase-js'
import { getRuntimeConfig, isSupabaseConfigured as hasSupabaseRuntimeConfig } from '../config/runtime'

const runtimeConfig = getRuntimeConfig()
const supabaseUrl = runtimeConfig.supabase_url || ''
const supabasePublishableKey = runtimeConfig.supabase_publishable_key || ''

export const isSupabaseConfigured = hasSupabaseRuntimeConfig()

export const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabasePublishableKey || 'placeholder-key',
)
