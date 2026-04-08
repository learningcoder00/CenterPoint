package com.centerpoint.viz.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.web.servlet.config.annotation.*;
import org.springframework.web.servlet.resource.*;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final AppProperties props;

    public WebConfig(AppProperties props) {
        this.props = props;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
            .allowedOrigins("*")
            .allowedMethods("*")
            .allowedHeaders("*");
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        Path root = props.projectRootPath();

        // /data/** -> projectRoot/data/ (symlink-following)
        registry.addResourceHandler("/data/**")
            .addResourceLocations("file:" + root.resolve("data") + "/")
            .setCacheControl(CacheControl.noCache())
            .resourceChain(false)
            .addResolver(new SymlinkFollowingResourceResolver());

        // /clip_preview/** -> projectRoot/clip_preview/
        registry.addResourceHandler("/clip_preview/**")
            .addResourceLocations("file:" + root.resolve("clip_preview") + "/")
            .setCacheControl(CacheControl.noCache())
            .resourceChain(false);

        // /assets/** -> Vue dist/assets/
        String vueDist = root.resolve(props.getVueDist()).toString();
        registry.addResourceHandler("/assets/**")
            .addResourceLocations("file:" + vueDist + "/assets/")
            .setCacheControl(CacheControl.noCache())
            .resourceChain(false);

        // Root files (index.html, favicon, etc.) from Vue dist
        registry.addResourceHandler("/*.html", "/*.ico", "/*.js", "/*.css", "/*.json", "/*.png", "/*.svg")
            .addResourceLocations("file:" + vueDist + "/")
            .setCacheControl(CacheControl.noCache())
            .resourceChain(false);
    }

    /**
     * Custom resolver that follows symlinks when resolving file: URLs.
     * Required because data/nuScenes is a symlink to the dataset mount.
     */
    static class SymlinkFollowingResourceResolver implements ResourceResolver {
        @Override
        public Resource resolveResource(
            jakarta.servlet.http.HttpServletRequest request,
            String requestPath, List<? extends Resource> locations, ResourceResolverChain chain
        ) {
            for (Resource location : locations) {
                try {
                    Resource relative = location.createRelative(requestPath);
                    if (relative instanceof FileSystemResource fsr) {
                        // Use toRealPath to follow symlinks
                        Path real = fsr.getFile().toPath().toRealPath();
                        FileSystemResource resolved = new FileSystemResource(real);
                        if (resolved.exists() && resolved.isReadable()) {
                            return resolved;
                        }
                    } else if (relative.exists() && relative.isReadable()) {
                        return relative;
                    }
                } catch (IOException e) {
                    // fall through
                }
            }
            return chain.resolveResource(request, requestPath, locations);
        }

        @Override
        public String resolveUrlPath(String resourcePath, List<? extends Resource> locations, ResourceResolverChain chain) {
            return chain.resolveUrlPath(resourcePath, locations);
        }
    }
}
