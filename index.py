from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json

from googleapiclient.discovery import build
import os

import streamlit as st
st.set_page_config(layout="wide")   
import plotly.express as px
import pandas as pd
import json
from datetime import datetime

print('Starting the script...')

watch_history = 'watch-history'
parsed_history = 'parsed_history'
video_metadata = 'video_metadata'

def prepare_source_data():
    st.write("Preparing source data...")

    # Load and parse the HTML file
    try:
        with open(f'{watch_history}.html', 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
        print('HTML file loaded successfully.')
    except FileNotFoundError:
        print(f'Error: {watch_history}.html file not found.')
        exit()

    video_list = []

    print('Extracting data from the watch history...')

    # Define the date range (last week)
    start_of_year = datetime(datetime.now().year, 1, 1)
    print('Date range defined: from', start_of_year, 'to', datetime.now())

    # Extract relevant information
    for entry in soup.find_all('div', class_='content-cell'):
        print(entry.prettify())  # Print the entry content for inspection
        
        title_tag = entry.find('a')
        date_text = None
        
        # Check for the last text node which contains the date
        for content in reversed(entry.contents):
            if isinstance(content, str) and content.strip():
                date_text = content.strip()
                break
        
        if title_tag and date_text:
            print('Found entry:', title_tag.text, date_text)
            # Remove timezone information
            date_text = ' '.join(date_text.split()[:-1])
            # Parse the date
            try:
                watched_date = datetime.strptime(date_text, '%d %b %Y, %H:%M:%S')
            except ValueError as e:
                print('Date parsing error for:', date_text, '-', e)
                continue

            if watched_date >= start_of_year:
                video = {
                    'title': title_tag.text,
                    'url': title_tag['href'],
                    'date': watched_date.strftime('%d %b %Y, %H:%M:%S')
                }
                video_list.append(video)

    # Save the extracted data to a new file
    if video_list:
        with open(f'{parsed_history}.json', 'w') as file:
            json.dump(video_list, file, indent=4, default=str)
        print(f'Data saved to {parsed_history}.json.')
    else:
        print('No videos found in the last week.')


    # Replace with your YouTube Data API key
    API_KEY = 'AIzaSyCmtSK7bsk89oXjKDhOu7hTfEcJ8EC-zIs'
    youtube = build('youtube', 'v3', developerKey=API_KEY)

    print ('Getting video metadata...')
    
    def get_video_metadata(video_id):
        request = youtube.videos().list(
            part='snippet,contentDetails,statistics',
            id=video_id
        )
        response = request.execute()
        return response['items'][0] if response['items'] else None

    # Load video list
    with open(f'{parsed_history}.json', 'r') as file:
        video_list = json.load(file)

    for video in video_list:
        video_id = video['url'].split('v=')[-1]
        metadata = get_video_metadata(video_id)
        if metadata:
            video['metadata'] = metadata

    # Save enriched video list
    with open(f'{video_metadata}.json', 'w') as file:
        json.dump(video_list, file, indent=4)
    print(f'Data saved to {video_metadata}.json.')

# Check if the file exists
if os.path.exists(f'{video_metadata}.json'):
    # Proceed with the Streamlit dashboard
    st.write(f"File '{video_metadata}.json' found. Proceeding with the dashboard.")

else:
    # Prepare source data
    print ('Preparing source data for ', who)
    prepare_source_data()

    # Load and prepare data

# Load and prepare data
@st.cache_data
def load_data():
    with open(f'{video_metadata}.json', 'r') as file:
        video_list = json.load(file)
    df = pd.DataFrame(video_list)
    return df

def prepare_data(df):
    df['date'] = pd.to_datetime(df['date'], format='%d %b %Y, %H:%M:%S')
    df['metadata'] = df['metadata'].apply(lambda x: x if isinstance(x, dict) else {})
    df['published_at'] = pd.to_datetime(df['metadata'].apply(lambda x: x['snippet']['publishedAt'] if 'snippet' in x and 'publishedAt' in x['snippet'] else None), errors='coerce')
    df['channel_title'] = df['metadata'].apply(lambda x: x['snippet']['channelTitle'] if 'snippet' in x and 'channelTitle' in x['snippet'] else None)
    df['view_count'] = df['metadata'].apply(lambda x: int(x['statistics']['viewCount']) if 'statistics' in x and 'viewCount' in x['statistics'] else None)
    df['like_count'] = df['metadata'].apply(lambda x: int(x['statistics']['likeCount']) if 'statistics' in x and 'likeCount' in x['statistics'] else None)
    df['comment_count'] = df['metadata'].apply(lambda x: int(x['statistics']['commentCount']) if 'statistics' in x and 'commentCount' in x['statistics'] else None)
    df['duration'] = df['metadata'].apply(lambda x: x['contentDetails']['duration'] if 'contentDetails' in x and 'duration' in x['contentDetails'] else None)
    df['tags'] = df['metadata'].apply(lambda x: x['snippet'].get('tags', []) if 'snippet' in x else [])
    df['category'] = df['metadata'].apply(lambda x: x['snippet']['categoryId'] if 'snippet' in x and 'categoryId' in x['snippet'] else None)
    return df

def parse_duration(duration):
    try:
        h, m, s = 0, 0, 0
        duration = duration.replace('PT', '')
        if 'H' in duration:
            h = int(duration.split('H')[0])
            duration = duration.split('H')[1]
        if 'M' in duration:
            m = int(duration.split('M')[0])
            duration = duration.split('M')[1]
        if 'S' in duration:
            s = int(duration.split('S')[0])
        return h * 3600 + m * 60 + s
    except Exception as e:
        return 0

def add_additional_features(df):
    df['duration_seconds'] = df['duration'].apply(parse_duration)
    df['duration_minutes'] = df['duration_seconds'] / 60
    df['hour'] = df['date'].dt.hour
    df['day'] = df['date'].dt.day_name()
    df['month'] = df['date'].dt.month_name()
    df['year'] = df['date'].dt.year
    df['week'] = df['date'].dt.to_period('W').apply(lambda r: r.start_time)
    return df

@st.cache_data
def get_category_names():
    with open('categories.json', 'r') as file:
        categories = json.load(file)
    return {item['id']: item['snippet']['title'] for item in categories['items']}

def filter_data(df, exclude_keywords, include_keywords):
    if exclude_keywords:
        exclude_list = [kw.strip().lower() for kw in exclude_keywords.split(',')]
        df = df[~df['metadata'].apply(lambda x: any(kw in json.dumps(x).lower() for kw in exclude_list))]
    if include_keywords:
        include_list = [kw.strip().lower() for kw in include_keywords.split(',')]
        df = df[df['metadata'].apply(lambda x: any(kw in json.dumps(x).lower() for kw in include_list))]
    return df

def plot_frequency_of_videos(df, mode):
    daily_counts = df['date'].dt.date.value_counts().sort_index()
    weekly_counts = df.groupby('week').size().reset_index(name='count')

    daily_tags = df.explode('tags').groupby(df['date'].dt.date)['tags'].value_counts().groupby(level=0).head(5).unstack().fillna(0)
    daily_tags = daily_tags.apply(lambda row: ', '.join(row.nlargest(5).index), axis=1)

    weekly_tags = df.explode('tags').groupby(df['week'])['tags'].value_counts().groupby(level=0).head(5).unstack().fillna(0)
    weekly_tags = weekly_tags.apply(lambda row: ', '.join(row.nlargest(5).index), axis=1)

    daily_fig = px.line(daily_counts, labels={'index': 'Date', 'value': 'Number of Videos Watched'}, title='Daily Frequency of YouTube Video Watching', color_discrete_sequence=['#636EFA'])
    daily_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)
    daily_fig.update_traces(hovertemplate='<b>%{x}</b><br>Number of Videos: %{y}<br>Top Tags: %{text}', text=daily_tags)

    weekly_fig = px.line(weekly_counts, x='week', y='count', labels={'week': 'Week', 'count': 'Number of Videos Watched'}, title='Weekly Frequency of YouTube Video Watching', color_discrete_sequence=['#636EFA'])
    weekly_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)
    weekly_fig.update_traces(hovertemplate='<b>Week %{x}</b><br>Number of Videos: %{y}<br>Top Tags: %{text}', text=weekly_tags)

    if mode == 'Overall':
        daily_counts_filtered = df.groupby(['date', 'keyword_group'])['date'].count().unstack(fill_value=0)
        daily_fig = px.line(daily_counts_filtered, labels={'index': 'Date', 'value': 'Number of Videos Watched'}, title='Daily Frequency of YouTube Video Watching', color_discrete_sequence=px.colors.qualitative.Set1)
        daily_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)
        
        weekly_counts_filtered = df.groupby(['week', 'keyword_group'])['week'].count().unstack(fill_value=0)
        weekly_fig = px.line(weekly_counts_filtered, labels={'index': 'Week', 'value': 'Number of Videos Watched'}, title='Weekly Frequency of YouTube Video Watching', color_discrete_sequence=px.colors.qualitative.Set1)
        weekly_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

    st.plotly_chart(daily_fig)
    st.plotly_chart(weekly_fig)

    # Add qualitative info for top 5 dates
    top_5_dates = daily_counts.nlargest(5).index
    top_5_videos = df[df['date'].dt.date.isin(top_5_dates)].groupby(df['date'].dt.date)['title'].apply(lambda x: ', '.join(x.head(3)))
    st.write("Top 5 dates with the most videos watched and examples of those videos:")
    for date, videos in top_5_videos.items():
        st.write(f"{date}: {videos}")

def plot_total_time_watching(df, mode):
    daily_duration = df.groupby(df['date'].dt.date)['duration_minutes'].sum().sort_index()
    weekly_duration = df.groupby('week')['duration_minutes'].sum().reset_index(name='total_duration')

    daily_fig = px.line(daily_duration, labels={'index': 'Date', 'value': 'Total Watching Time (minutes)'}, title='Daily Total Time Watching YouTube Videos', color_discrete_sequence=['#EF553B'])
    daily_fig.update_layout(title_x=0.5, showlegend=False, width=1600)

    weekly_fig = px.line(weekly_duration, x='week', y='total_duration', labels={'week': 'Week', 'total_duration': 'Total Watching Time (minutes)'}, title='Weekly Total Time Watching YouTube Videos', color_discrete_sequence=['#EF553B'])
    weekly_fig.update_layout(title_x=0.5, showlegend=False, width=1600)

    if mode == 'Overall':
        daily_duration_filtered = df.groupby(['date', 'keyword_group'])['duration_minutes'].sum().unstack(fill_value=0)
        daily_fig = px.line(daily_duration_filtered, labels={'index': 'Date', 'value': 'Total Watching Time (minutes)'}, title='Daily Total Time Watching YouTube Videos', color_discrete_sequence=px.colors.qualitative.Set1)
        daily_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

        weekly_duration_filtered = df.groupby(['week', 'keyword_group'])['duration_minutes'].sum().unstack(fill_value=0)
        weekly_fig = px.line(weekly_duration_filtered, labels={'index': 'Week', 'total_duration': 'Total Watching Time (minutes)'}, title='Weekly Total Time Watching YouTube Videos', color_discrete_sequence=px.colors.qualitative.Set1)
        weekly_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

    st.plotly_chart(daily_fig)
    st.plotly_chart(weekly_fig)

def plot_average_video_duration(df, mode):
    daily_avg_duration = df.groupby(df['date'].dt.date)['duration_minutes'].mean().sort_index()
    weekly_avg_duration = df.groupby('week')['duration_minutes'].mean().reset_index(name='avg_duration')

    daily_fig = px.line(daily_avg_duration, labels={'index': 'Date', 'value': 'Average Video Duration (minutes)'}, title='Daily Average Video Duration Over Time', color_discrete_sequence=['#00CC96'])
    daily_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

    weekly_fig = px.line(weekly_avg_duration, x='week', y='avg_duration', labels={'week': 'Week', 'avg_duration': 'Average Video Duration (minutes)'}, title='Weekly Average Video Duration Over Time', color_discrete_sequence=['#00CC96'])
    weekly_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

    if mode == 'Overall':
        daily_avg_duration_filtered = df.groupby(['date', 'keyword_group'])['duration_minutes'].mean().unstack(fill_value=0)
        daily_fig = px.line(daily_avg_duration_filtered, labels={'index': 'Date', 'value': 'Average Video Duration (minutes)'}, title='Daily Average Video Duration Over Time', color_discrete_sequence=px.colors.qualitative.Set1)
        daily_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

        weekly_avg_duration_filtered = df.groupby(['week', 'keyword_group'])['duration_minutes'].mean().unstack(fill_value=0)
        weekly_fig = px.line(weekly_avg_duration_filtered, labels={'index': 'Week', 'avg_duration': 'Average Video Duration (minutes)'}, title='Weekly Average Video Duration Over Time', color_discrete_sequence=px.colors.qualitative.Set1)
        weekly_fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)

    st.plotly_chart(daily_fig)
    st.plotly_chart(weekly_fig)

    # Add a new option to show count of videos by week and duration bins
    duration_bins = [0, 1, 5, 15, 30, 60, 120, float('inf')]
    duration_labels = ["<1 min", "1-5 min", "5-15 min", "15-30 min", "30-60 min", "1-2 hr", ">2 hr"]
    df['duration_bin'] = pd.cut(df['duration_minutes'], bins=duration_bins, labels=duration_labels)
    count_by_week = df.groupby(['week', 'duration_bin']).size().reset_index(name='count')
    fig_count_by_week = px.bar(count_by_week, x='week', y='count', color='duration_bin', title='Count of Videos by Week and Duration', barmode='stack')
    fig_count_by_week.update_layout(width=1600)
    st.plotly_chart(fig_count_by_week)

def plot_most_watched_categories(df, category_names, mode):
    df['category_name'] = df['category'].map(category_names)
    category_counts = df['category_name'].value_counts()

    daily_category_counts = df.groupby([df['date'].dt.date, 'category_name']).size().unstack(fill_value=0)
    weekly_category_counts = df.groupby([df['week'], 'category_name']).size().unstack(fill_value=0)

    daily_fig = px.bar(daily_category_counts, 
                       labels={'index': 'Date', 'value': 'Number of Videos Watched', 'variable': 'Category'},
                       title='Daily Most Watched Categories',
                       color_discrete_sequence=px.colors.qualitative.Plotly)
    daily_fig.update_layout(xaxis={'categoryorder': 'total descending'}, title_x=0.5, barmode='stack', width=1600)

    weekly_fig = px.bar(weekly_category_counts, 
                        labels={'index': 'Week', 'value': 'Number of Videos Watched', 'variable': 'Category'},
                        title='Weekly Most Watched Categories',
                        color_discrete_sequence=px.colors.qualitative.Plotly)
    weekly_fig.update_layout(xaxis={'categoryorder': 'total descending'}, title_x=0.5, barmode='stack', width=1600)

    if mode == 'Overall':
        weekly_category_counts_filtered = df.groupby(['week', 'keyword_group', 'category_name']).size().unstack(fill_value=0)
        weekly_fig = px.bar(weekly_category_counts_filtered, labels={'index': 'Week', 'value': 'Number of Videos Watched', 'variable': 'Category'}, title='Weekly Most Watched Categories', color_discrete_sequence=px.colors.qualitative.Plotly)
        weekly_fig.update_layout(xaxis={'categoryorder': 'total descending'}, title_x=0.5, barmode='stack', width=1600)

    st.plotly_chart(daily_fig)
    st.plotly_chart(weekly_fig)

    # Add qualitative info for top 5 categories
    top_5_categories = category_counts.nlargest(5).index
    top_5_videos_per_category = df[df['category_name'].isin(top_5_categories)].groupby('category_name')['title'].apply(lambda x: ', '.join(x.head(3)))
    st.write("Top 5 categories and examples of videos in each:")
    for category, videos in top_5_videos_per_category.items():
        st.write(f"{category}: {videos}")

def plot_watching_time_heatgrid(df, mode):
    df['day_hour'] = df['date'].dt.floor('H')
    heatmap_data_daily = df.groupby([df['day_hour'].dt.date, df['day_hour'].dt.hour]).size().unstack(fill_value=0)
    heatmap_data_weekly = df.groupby([df['week'], df['day_hour'].dt.hour]).size().unstack(fill_value=0)

    daily_fig = px.imshow(heatmap_data_daily.T, 
                          labels=dict(x="Date", y="Hour of Day", color="Number of Videos Watched"),
                          title='Daily Watching Time of the Day',
                          color_continuous_scale='Viridis')
    daily_fig.update_layout(title_x=0.5, width=1600)

    weekly_fig = px.imshow(heatmap_data_weekly.T, 
                           labels=dict(x="Week", y="Hour of Day", color="Number of Videos Watched"),
                           title='Weekly Watching Time of the Day',
                           color_continuous_scale='Viridis')
    weekly_fig.update_layout(title_x=0.5, width=1600)

    # Add top 3 videos by duration on hover
    hover_text = df.groupby([df['week'], df['hour']]).apply(lambda x: ', '.join(x.nlargest(3, 'duration_minutes')['title']))
    weekly_fig.update_traces(hovertemplate='<b>Week %{x}</b><br>Hour: %{y}<br>Number of Videos: %{z}<br>Top 3 Videos: %{text}', text=hover_text)

    if mode == 'Overall':
        heatmap_data_weekly_filtered = df.groupby(['week', 'keyword_group', 'day_hour']).size().unstack(fill_value=0)
        weekly_fig = px.imshow(heatmap_data_weekly_filtered.T, labels=dict(x="Week", y="Hour of Day", color="Number of Videos Watched"), title='Weekly Watching Time of the Day', color_continuous_scale='Viridis')
        weekly_fig.update_layout(title_x=0.5, width=1600)

    st.plotly_chart(daily_fig)
    st.plotly_chart(weekly_fig)

def plot_video_duration_distribution(df):
    bins = [0, 1, 5, 15, 30, 60, 120, 180, float('inf')]
    labels = ["<1 min", "1-5 min", "5-15 min", "15-30 min", "30-60 min", "1-2 hr", "2-3 hr", ">3 hr"]
    df['duration_bins'] = pd.cut(df['duration_minutes'], bins=bins, labels=labels, right=False)

    fig = px.histogram(df, x='duration_bins', 
                       labels={'duration_bins': 'Duration', 'count': 'Number of Videos Watched'},
                       title='Video Duration Distribution',
                       category_orders={'duration_bins': labels},
                       color_discrete_sequence=['#FFA15A'])
    fig.update_layout(title_x=0.5, legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=14)), width=1600)
    st.plotly_chart(fig)

    # Add interesting slices for video duration distribution
    df['category_name'] = df['category'].map(category_names)
    
    category_duration_dist = df.groupby(['category_name', 'duration_bins']).size().unstack(fill_value=0)
    fig_category_duration_dist = px.bar(category_duration_dist, title='Video Duration Distribution by Category', barmode='stack')
    fig_category_duration_dist.update_layout(width=1600)
    st.plotly_chart(fig_category_duration_dist)

    tag_duration_dist = df.explode('tags').groupby(['tags', 'duration_bins']).size().unstack(fill_value=0)
    fig_tag_duration_dist = px.bar(tag_duration_dist, title='Video Duration Distribution by Top Tags', barmode='stack')
    fig_tag_duration_dist.update_layout(width=1600)
    st.plotly_chart(fig_tag_duration_dist)

    date_duration_dist = df.groupby([df['date'].dt.date, 'duration_bins']).size().unstack(fill_value=0)
    fig_date_duration_dist = px.bar(date_duration_dist, title='Video Duration Distribution by Date', barmode='stack')
    fig_date_duration_dist.update_layout(width=1600)
    st.plotly_chart(fig_date_duration_dist)

def plot_seasonal_shift(df, mode):
    weekly_data = df.explode('tags').groupby(['week', 'tags']).agg({'title':'count', 'duration_minutes':'sum'}).reset_index()
    fig = px.scatter(weekly_data, 
                     x='week', 
                     y='title', 
                     size='duration_minutes', 
                     color='tags', 
                     hover_name='tags',
                     labels={'week': 'Week', 'title': 'Number of Videos Watched', 'tags': 'Tag'},
                     title='Revealed Preferences (All Tags by Week)')
    fig.update_layout(title_x=0.5, showlegend=False, width=1600)
    st.plotly_chart(fig)

    # Plot all tags by number of videos
    all_tags = df.explode('tags')['tags'].value_counts()
    fig_all_tags = px.bar(all_tags, 
                          labels={'index': 'Tag', 'value': 'Number of Videos Watched'},
                          title='Top Tags by Number of Videos Watched',
                          color_discrete_sequence=px.colors.qualitative.Plotly)
    fig_all_tags.update_layout(xaxis={'categoryorder': 'total descending'}, title_x=0.5, width=1600)
    st.plotly_chart(fig_all_tags)

    # Plot top 10 tags by number of videos
    top_10_tags = df.explode('tags')['tags'].value_counts().nlargest(10)
    fig_top_10_tags = px.bar(top_10_tags, 
                             labels={'index': 'Tag', 'value': 'Number of Videos Watched'},
                             title='Top 10 Tags by Number of Videos Watched',
                             color_discrete_sequence=px.colors.qualitative.Plotly)
    fig_top_10_tags.update_layout(xaxis={'categoryorder': 'total descending'}, title_x=0.5, width=1600)
    st.plotly_chart(fig_top_10_tags)

def plot_video_duration_curve(df):
    fig = px.histogram(df, x='duration_minutes', 
                       labels={'duration_minutes': 'Video Duration (minutes)', 'count': 'Number of Videos Watched'},
                       title='Video Duration Curve',
                       color_discrete_sequence=['#FFA15A'])
    fig.update_layout(title_x=0.5, width=1600)
    st.plotly_chart(fig)

def plot_videos_by_day_of_week(df, mode):
    videos_by_day = df['day'].value_counts().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    fig_videos_by_day = px.bar(videos_by_day,
                               labels={'index': 'Day of the Week', 'value': 'Number of Videos Watched'},
                               title='Number of Videos Watched by Day of the Week',
                               color_discrete_sequence=['#636EFA'])
    fig_videos_by_day.update_layout(title_x=0.5, showlegend=False, width=1600)
    st.plotly_chart(fig_videos_by_day)

    duration_by_day = df.groupby('day')['duration_minutes'].mean().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    fig_duration_by_day = px.bar(duration_by_day,
                                 labels={'index': 'Day of the Week', 'duration_minutes': 'Average Duration (minutes)'},
                                 title='Average Duration of Videos Watched by Day of the Week',
                                 color_discrete_sequence=['#EF553B'])
    fig_duration_by_day.update_layout(title_x=0.5, showlegend=False, width=1600)
    st.plotly_chart(fig_duration_by_day)

# Main script
df = load_data()
df = prepare_data(df)
df = add_additional_features(df)
category_names = get_category_names()

st.title('YouTube Watch History Analysis')

# Sidebar for navigation
st.sidebar.title("Navigation")
exclude_keywords = st.sidebar.text_input("Comma-separated keywords to filter out videos")
include_keywords = st.sidebar.text_input("Comma-separated keywords to filter in videos")
filtered_df = filter_data(df, exclude_keywords, include_keywords)

chart_option = st.sidebar.radio(
    "Select a chart:",
    ('Frequency of YouTube Video Watching', 
     'Total Time Watching YouTube Videos',
     'Average Video Duration Over Time',
     'Most Watched Categories',
     'Watching Time of Day',
     'Video Duration Distribution',
     'Video Duration Curve',
     'Videos Watched and Duration by Day of the Week',
     'Revealed Preferences'))

# Frequency of YouTube video watching
if chart_option == 'Frequency of YouTube Video Watching':
    st.header('Frequency of YouTube Video Watching')
    plot_frequency_of_videos(filtered_df, exclude_keywords)

# Total time video watching
elif chart_option == 'Total Time Watching YouTube Videos':
    st.header('Total Time Watching YouTube Videos')
    plot_total_time_watching(filtered_df, exclude_keywords)

# Average video duration over time
elif chart_option == 'Average Video Duration Over Time':
    st.header('Average Video Duration Over Time')
    plot_average_video_duration(filtered_df, exclude_keywords)

# Most watched categories
elif chart_option == 'Most Watched Categories':
    st.header('Most Watched Categories')
    plot_most_watched_categories(filtered_df, category_names, exclude_keywords)

# Watching time of the day as a heatgrid
elif chart_option == 'Watching Time of Day':
    st.header('Watching Time of Day')
    plot_watching_time_heatgrid(filtered_df, exclude_keywords)

# Video duration distribution
elif chart_option == 'Video Duration Distribution':
    st.header('Video Duration Distribution')
    plot_video_duration_distribution(filtered_df)

# Video duration curve
elif chart_option == 'Video Duration Curve':
    st.header('Video Duration Curve')
    plot_video_duration_curve(filtered_df)

# Videos watched and duration by day of the week
elif chart_option == 'Videos Watched and Duration by Day of the Week':
    st.header('Videos Watched and Duration by Day of the Week')
    plot_videos_by_day_of_week(filtered_df, exclude_keywords)

# Revealed Preferences (previously Seasonal shift in YouTube consumption)
elif chart_option == 'Revealed Preferences':
    st.header('Revealed Preferences')
    plot_seasonal_shift(filtered_df, exclude_keywords)
