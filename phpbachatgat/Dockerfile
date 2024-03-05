# Use the official PHP with Apache image
FROM php:7.4-apache

# Set the working directory
WORKDIR /var/www/html

# Install dependencies
RUN apt-get update && \
    apt-get install -y git zip unzip libonig-dev libxml2-dev && \
    docker-php-ext-install pdo_mysql mbstring xml

# Install Composer
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Copy the Laravel application files
COPY . .

# Install dependencies
# RUN composer install --no-interaction --no-scripts --no-dev

# Generate application key
# RUN php artisan key:generate

# # Set permissions
# RUN chown -R www-data:www-data storage bootstrap/cache

# Expose port 80
EXPOSE 80

# Start Apache
CMD ["apache2-foreground"]