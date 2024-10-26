package com.sopotek.backend;

import org.jetbrains.annotations.NotNull;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        // Configure CORS
        http.cors(cors -> cors.configurationSource(corsConfigurationSource()));

        // Disable CSRF
        http.csrf(AbstractHttpConfigurer::disable);

        // Configure authorization requests
        http.authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/**").permitAll()  // Public endpoint
                .anyRequest().authenticated()  // Other endpoints require authentication
        );

        // Return the configured SecurityFilterChain
        return http.build();
    }

    // Define the CORS configuration source as a separate bean
    private @NotNull CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.addAllowedOrigin("http://localhost:3000");
        configuration.addAllowedOriginPattern("https://localhost:3000/**");


        configuration.addAllowedOrigin("https://www.tradeadviser.org");
        configuration.addAllowedOriginPattern("https://tradeadviser.org/**");
        configuration.addAllowedMethod("*");
        configuration.addAllowedHeader("*");
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

}
